import { useRef, useState } from "react";
import { LoaderCircle, Mic, Square } from "lucide-react";

const SpeechRecognition =
  window.SpeechRecognition ?? window.webkitSpeechRecognition;
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";
const MAX_AUDIO_BYTES = 25 * 1024 * 1024;

function writeWav(audioBuffer) {
  const targetRate = 16000;
  const frameCount = Math.ceil(audioBuffer.duration * targetRate);
  const offlineContext = new OfflineAudioContext(1, frameCount, targetRate);
  const source = offlineContext.createBufferSource();
  source.buffer = audioBuffer;
  source.connect(offlineContext.destination);
  source.start();

  return offlineContext.startRendering().then((monoBuffer) => {
    const samples = monoBuffer.getChannelData(0);
    const bytesPerSample = 2;
    const dataSize = samples.length * bytesPerSample;
    const wav = new ArrayBuffer(44 + dataSize);
    const view = new DataView(wav);
    const writeText = (offset, text) => {
      for (let index = 0; index < text.length; index += 1) {
        view.setUint8(offset + index, text.charCodeAt(index));
      }
    };

    writeText(0, "RIFF");
    view.setUint32(4, 36 + dataSize, true);
    writeText(8, "WAVE");
    writeText(12, "fmt ");
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
    view.setUint32(24, targetRate, true);
    view.setUint32(28, targetRate * bytesPerSample, true);
    view.setUint16(32, bytesPerSample, true);
    view.setUint16(34, 16, true);
    writeText(36, "data");
    view.setUint32(40, dataSize, true);

    for (let index = 0; index < samples.length; index += 1) {
      const sample = Math.max(-1, Math.min(1, samples[index]));
      view.setInt16(
        44 + index * bytesPerSample,
        sample < 0 ? sample * 0x8000 : sample * 0x7fff,
        true,
      );
    }

    return new Blob([wav], { type: "audio/wav" });
  });
}

async function convertToWav(recording) {
  const AudioContextClass = window.AudioContext ?? window.webkitAudioContext;
  if (!AudioContextClass || !window.OfflineAudioContext) {
    throw new Error("Este navegador no puede preparar el audio para Gemini.");
  }

  const context = new AudioContextClass();
  try {
    const decoded = await context.decodeAudioData(await recording.arrayBuffer());
    return await writeWav(decoded);
  } finally {
    await context.close();
  }
}

export default function App() {
  const [isRecording, setIsRecording] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [status, setStatus] = useState("Listo para grabar");
  const [statusKind, setStatusKind] = useState("idle");
  const [liveTranscript, setLiveTranscript] = useState("");
  const [geminiTranscript, setGeminiTranscript] = useState("");
  const [liveAvailable, setLiveAvailable] = useState(Boolean(SpeechRecognition));
  const streamRef = useRef(null);
  const recorderRef = useRef(null);
  const recognitionRef = useRef(null);
  const chunksRef = useRef([]);
  const finalTextRef = useRef("");
  const recordingRef = useRef(false);

  const showStatus = (message, kind = "idle") => {
    setStatus(message);
    setStatusKind(kind);
  };

  const transcribeWithGemini = async (recording) => {
    setIsProcessing(true);
    showStatus("Preparando audio para Gemini…", "processing");
    try {
      const wav = await convertToWav(recording);
      if (wav.size > MAX_AUDIO_BYTES) {
        throw new Error("El audio supera el límite de 25 MB.");
      }

      showStatus("Gemini está transcribiendo el audio…", "processing");
      const response = await fetch(`${API_BASE_URL}/transcribe`, {
        method: "POST",
        headers: { "Content-Type": "audio/wav" },
        body: wav,
      });
      const result = await response.json();
      if (!response.ok) {
        throw new Error(result.error ?? "Gemini no pudo transcribir el audio.");
      }

      setGeminiTranscript(result.transcription ?? "Gemini no devolvió texto.");
      showStatus(`Transcripción completada con ${result.model ?? "Gemini"}.`, "success");
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "No se pudo enviar el audio.";
      showStatus(message, "error");
    } finally {
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      recorderRef.current = null;
      setIsProcessing(false);
    }
  };

  const startRecording = async () => {
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      showStatus("Este navegador no permite grabar audio. Prueba Chrome o Safari.", "error");
      return;
    }

    try {
      showStatus("Solicitando acceso al micrófono…", "processing");
      setIsProcessing(true);
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      chunksRef.current = [];
      finalTextRef.current = "";
      setLiveTranscript("");
      setGeminiTranscript("");

      const mimeType = ["audio/webm;codecs=opus", "audio/mp4", "audio/webm"].find(
        (type) => MediaRecorder.isTypeSupported(type),
      );
      const recorder = mimeType
        ? new MediaRecorder(stream, { mimeType })
        : new MediaRecorder(stream);
      recorderRef.current = recorder;
      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data);
      };
      recorder.onstop = () => {
        const recording = new Blob(chunksRef.current, {
          type: recorder.mimeType || "audio/webm",
        });
        void transcribeWithGemini(recording);
      };
      recorder.start(250);

      recordingRef.current = true;
      setIsRecording(true);
      setIsProcessing(false);
      showStatus(
        SpeechRecognition
          ? "Escuchando y transcribiendo en vivo"
          : "Grabando; el navegador no tiene transcripción en vivo",
        "recording",
      );

      if (SpeechRecognition) {
        const recognition = new SpeechRecognition();
        recognitionRef.current = recognition;
        recognition.lang = "es-ES";
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.onresult = (event) => {
          let interim = "";
          for (let index = event.resultIndex; index < event.results.length; index += 1) {
            const result = event.results[index];
            const text = result[0].transcript.trim();
            if (result.isFinal) {
              finalTextRef.current = `${finalTextRef.current} ${text}`.trim();
            } else {
              interim = `${interim} ${text}`.trim();
            }
          }
          setLiveTranscript(`${finalTextRef.current} ${interim}`.trim());
        };
        recognition.onerror = (event) => {
          setLiveAvailable(false);
          showStatus(
            `Transcripción en vivo: ${event.error}. La grabación puede continuar para Gemini.`,
            "error",
          );
        };
        recognition.onend = () => {
          if (recordingRef.current) {
            try {
              recognition.start();
            } catch {
              setLiveAvailable(false);
            }
          }
        };
        try {
          recognition.start();
        } catch (error) {
          setLiveAvailable(false);
          showStatus(
            `No se pudo iniciar la transcripción en vivo: ${error.message}`,
            "error",
          );
        }
      } else {
        setLiveAvailable(false);
      }
    } catch (error) {
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      setIsRecording(false);
      setIsProcessing(false);
      const message =
        error instanceof Error ? error.message : "No se pudo acceder al micrófono.";
      showStatus(`No se pudo iniciar la grabación: ${message}`, "error");
    }
  };

  const stopRecording = () => {
    if (!recordingRef.current) return;
    recordingRef.current = false;
    setIsRecording(false);
    setIsProcessing(true);
    showStatus("Cerrando grabación…", "processing");
    recognitionRef.current?.stop();
    recognitionRef.current = null;
    if (recorderRef.current?.state === "recording") {
      recorderRef.current.stop();
    } else {
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      setIsProcessing(false);
    }
  };

  const toggleRecording = () => {
    if (isProcessing) return;
    if (isRecording) stopRecording();
    else void startRecording();
  };

  return (
    <main className="app-shell">
      <header className="masthead">
        <div className="brand-mark" aria-hidden="true">V/T</div>
        <span className="masthead-label">VOZ A TEXTO <span>·</span> ESPAÑOL</span>
      </header>

      <section className="workspace" aria-labelledby="page-title">
        <div className="intro-block">
          <p className="eyebrow">TRANSCRIPCIÓN INSTANTÁNEA</p>
          <h1 id="page-title">Una voz,<br />texto claro.</h1>
          <p className="lede">Habla con naturalidad. Las palabras aparecen mientras hablas.</p>
        </div>

        <div className="recording-control">
          <div className={`status-line status-${statusKind}`} role="status" aria-live="polite">
            <span className="status-light" />
            <span>{status}</span>
          </div>
          <button
            className={`record-button${isRecording ? " is-recording" : ""}${isProcessing ? " is-processing" : ""}`}
            type="button"
            onClick={toggleRecording}
            disabled={isProcessing}
            aria-label={isRecording ? "Detener grabación" : "Empezar a hablar"}
            aria-pressed={isRecording}
          >
            {isProcessing ? <LoaderCircle className="button-icon spin" /> : isRecording ? <Square className="button-icon" fill="currentColor" /> : <Mic className="button-icon" />}
          </button>
          <span className="button-caption">
            {isProcessing ? "PROCESANDO" : isRecording ? "DETENER" : "EMPEZAR A HABLAR"}
          </span>
        </div>

        <section className="transcript-panel" aria-label="Transcripción en vivo">
          <div className="panel-heading">
            <span>EN VIVO</span>
            <span className="language-chip">ES</span>
          </div>
          <p className={`live-text${liveTranscript ? " has-text" : " is-empty"}`}>
            {liveTranscript || (isRecording ? "Escuchando…" : "Tu transcripción aparecerá aquí.")}
          </p>
        </section>

        {geminiTranscript && (
          <section className="gemini-panel" aria-label="Transcripción de Gemini">
            <div className="panel-heading"><span>GEMINI · AUDIO COMPLETO</span></div>
            <p className="gemini-text">{geminiTranscript}</p>
          </section>
        )}

        {!liveAvailable && !SpeechRecognition && (
          <p className="compatibility-note">
            Este navegador no ofrece transcripción en vivo. Puedes grabar y obtener el resultado de Gemini.
          </p>
        )}
      </section>

      <footer className="page-footer">
        <span>WEB SPEECH API</span>
        <span className="footer-divider" />
        <span>GEMINI POR LOTES</span>
      </footer>
    </main>
  );
}
