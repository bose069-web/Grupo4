const recordButton = document.querySelector('#recordButton');
const recordLabel = document.querySelector('#recordLabel');
const captureMode = document.querySelector('#captureMode');
const captureHint = document.querySelector('#captureHint');
const capturePanel = document.querySelector('.capture-panel');
const finalText = document.querySelector('#finalText');
const interimText = document.querySelector('#interimText');
const placeholder = document.querySelector('#placeholder');
const wordCount = document.querySelector('#wordCount');
const timer = document.querySelector('#timer');
const browserNotice = document.querySelector('#browserNotice');
const tests = [...document.querySelectorAll('.test-card')];
let recognition;
let mediaRecorder;
let timerId;
let seconds = 0;
let isRecording = false;
let speechFailed = false;
let currentTest = 1;
const results = {};
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
function showNotice(message) { browserNotice.textContent = message; browserNotice.hidden = false; }
function updateTimer() { seconds += 1; timer.textContent = `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`; }
function updateWordCount() { const text = finalText.textContent.trim(); const count = text ? text.split(/\s+/).length : 0; wordCount.textContent = `${count} ${count === 1 ? 'palabra' : 'palabras'}`; }
function setResult(text) { results[currentTest] = text; const card = tests[currentTest - 1]; card.querySelector('.test-state').textContent = text ? 'completada' : 'pendiente'; card.querySelector('.test-state').style.color = text ? '#4d8b57' : ''; }
function stopRecording() { isRecording = false; clearInterval(timerId); capturePanel.classList.remove('recording'); recordLabel.textContent = 'iniciar grabación'; recordButton.setAttribute('aria-label', 'Iniciar grabación'); captureMode.textContent = 'GRABACIÓN FINALIZADA'; captureHint.textContent = 'Selecciona otra prueba o descarga el informe con tus resultados.'; if (recognition) recognition.stop(); if (mediaRecorder && mediaRecorder.state !== 'inactive') mediaRecorder.stop(); setResult(finalText.textContent.trim()); }
async function startRecognition() { speechFailed = false; recognition = new SpeechRecognition(); recognition.lang = 'es-ES'; recognition.continuous = true; recognition.interimResults = true; try { if ('processLocally' in recognition) { const availability = await SpeechRecognition.available({ langs: ['es-ES'], processLocally: true }); if (availability === 'downloadable') await SpeechRecognition.install({ langs: ['es-ES'] }); if (availability === 'available' || availability === 'downloadable' || availability === 'downloading') recognition.processLocally = true; } } catch (error) { recognition.processLocally = false; }
	recognition.onresult = event => { let interim = ''; for (let index = event.resultIndex; index < event.results.length; index += 1) { const transcript = event.results[index][0].transcript; if (event.results[index].isFinal) finalText.textContent += `${transcript} `; else interim += transcript; } placeholder.hidden = Boolean(finalText.textContent || interim); interimText.textContent = interim; updateWordCount(); };
	recognition.onerror = event => { if (event.error === 'not-allowed') showNotice('El acceso al micrófono fue bloqueado. Permítelo en la configuración del navegador para continuar.'); else if (event.error === 'language-not-supported') { speechFailed = true; showNotice('El paquete de idioma español no está disponible en este navegador. Instala el idioma español o usa Chrome actualizado.'); } else if (event.error === 'network' || event.error === 'service-not-allowed') { speechFailed = true; showNotice('El reconocimiento local no está disponible y el servicio online de voz está bloqueado en este navegador. Abre el proyecto en Chrome actualizado.'); } else if (event.error !== 'aborted') showNotice(`La transcripción no pudo continuar (${event.error}).`); };
	recognition.onend = () => { if (isRecording && !speechFailed) recognition.start(); };
	recognition.start();
}
async function startRecording() { if (location.protocol === 'file:') { showNotice('Abre el proyecto desde http://localhost:8000. Web Speech API no funciona de forma fiable abriendo el HTML directamente.'); return; } if (!SpeechRecognition) { showNotice('Este navegador no ofrece Web Speech API. Prueba con Google Chrome o Microsoft Edge.'); return; } try { const stream = await navigator.mediaDevices.getUserMedia({ audio: true }); mediaRecorder = new MediaRecorder(stream); mediaRecorder.onstop = () => stream.getTracks().forEach(track => track.stop()); mediaRecorder.start(); isRecording = true; seconds = 0; timer.textContent = '00:00'; timerId = setInterval(updateTimer, 1000); capturePanel.classList.add('recording'); recordLabel.textContent = 'detener grabación'; recordButton.setAttribute('aria-label', 'Detener grabación'); captureMode.textContent = 'GRABANDO AHORA'; captureHint.textContent = 'Habla con claridad y a un ritmo natural.'; startRecognition(); } catch (error) { showNotice('No se pudo acceder al micrófono. Comprueba los permisos del sitio y vuelve a intentarlo.'); } }
recordButton.addEventListener('click', () => { if (isRecording) stopRecording(); else startRecording(); });
document.querySelector('#clearButton').addEventListener('click', () => { finalText.textContent = ''; interimText.textContent = ''; placeholder.hidden = false; updateWordCount(); setResult(''); });
tests.forEach(card => card.addEventListener('click', () => { if (isRecording) stopRecording(); tests.forEach(item => item.classList.remove('active')); card.classList.add('active'); currentTest = Number(card.dataset.test); finalText.textContent = results[currentTest] || ''; interimText.textContent = ''; placeholder.hidden = Boolean(finalText.textContent); updateWordCount(); captureMode.textContent = 'LISTO PARA GRABAR'; captureHint.textContent = `Prueba ${String(currentTest).padStart(2, '0')} seleccionada. Pulsa el botón para comenzar.`; }));
document.querySelector('#downloadButton').addEventListener('click', () => { const report = ['DÍA 7 | SERVICIOS DE VOZ E INTERFACES', '', ...tests.map((card, index) => `${card.querySelector('h3').textContent}: ${results[index + 1] || '[sin transcripción]'}`), '', 'OBSERVACIONES:', document.querySelector('#notes').value || '[sin notas]'].join('\n'); const blob = new Blob([report], { type: 'text/plain;charset=utf-8' }); const link = document.createElement('a'); link.href = URL.createObjectURL(blob); link.download = 'informe-speech-to-text.txt'; link.click(); URL.revokeObjectURL(link.href); document.querySelector('#saveState').textContent = 'informe descargado'; });
if (location.protocol === 'file:') showNotice('Para transcribir, abre esta página desde http://localhost:8000 en Chrome o Edge y permite el micrófono.');
else if (/Electron|Code\//.test(navigator.userAgent)) showNotice('El navegador integrado de VS Code bloquea el servicio de voz. Copia http://localhost:8000 y ábrelo en Google Chrome o Microsoft Edge de escritorio.');
else if (!navigator.mediaDevices || !SpeechRecognition) showNotice('Para utilizar todas las funciones, abre esta página en Chrome o Edge mediante localhost y permite el micrófono.');
