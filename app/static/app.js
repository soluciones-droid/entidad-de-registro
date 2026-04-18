/**
 * ER RA - Single Page Application Logic
 */

const API_BASE = '/api/v1';
const RA_API_KEY = 'dev-ra-key'; // En prod, esto se pediría al usuario

// --- Application State ---
const state = {
    currentView: 'home',
    requests: [],
    loading: false,
    registration: {
        dni: '',
        given_name: '',
        first_surname: '',
        second_surname: '',
        email: '',
        certificate_profile: 'natural_person',
        issuance_mode: 'local',
        csr_pem: '',
        consent_text: 'Autorizo el tratamiento de mis datos para la emision del certificado digital.',
        images: {
            dni_front: null,
            dni_back: null,
            selfie: null,
            liveness: null
        }
    }
};

// --- Router ---
const router = {
    navigate(view) {
        state.currentView = view;
        this.updateNav();
        this.render();
    },
    updateNav() {
        document.querySelectorAll('.nav-btn').forEach(btn => {
            btn.classList.remove('active');
        });
        const activeBtn = document.getElementById(`nav-${state.currentView}`);
        if (activeBtn) activeBtn.classList.add('active');
    },
    render() {
        const container = document.getElementById('view-container');
        container.classList.remove('fade-in');
        void container.offsetWidth; // Trigger reflow
        container.classList.add('fade-in');

        // Check for mobile session in URL
        const params = new URLSearchParams(window.location.search);
        const sessionId = params.get('session');

        if (sessionId) {
            container.innerHTML = views.mobileCapture(sessionId);
            setTimeout(() => webcam.initMobile(sessionId), 100);
            return;
        }

        switch (state.currentView) {
            case 'home':
                container.innerHTML = views.home();
                break;
            case 'register':
                container.innerHTML = views.register();
                break;
            case 'dashboard':
                container.innerHTML = views.dashboard();
                api.fetchRequests();
                break;
            default:
                container.innerHTML = '<h1>404</h1>';
        }
        lucide.createIcons();
    }
};

// --- API Client ---
const api = {
    async fetchRequests(status = '') {
        state.loading = true;
        this.renderTable();
        try {
            const response = await fetch(`${API_BASE}/requests?status=${status}`, {
                headers: { 'X-API-Key': RA_API_KEY }
            });
            if (!response.ok) throw new Error(`Status: ${response.status}`);
            state.requests = await response.json();
            state.loading = false; // CORRECCIÓN: Apagar carga ANTES de renderizar
            this.renderTable();
            this.updateStats();
        } catch (err) {
            console.error('Fetch Error:', err);
            ui.toast('Error al cargar solicitudes: ' + err.message, 'danger');
            state.requests = [];
            state.loading = false;
            this.renderTable();
        }
    },
    renderTable() {
        const tbody = document.getElementById('request-table-body');
        if (!tbody) return;
        
        // Si el estado es de carga, mostrar spinner
        if (state.loading) {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center"><div class="spinner" style="width:20px;height:20px;margin:auto"></div> Cargando...</td></tr>';
            return;
        }

        // Si no hay solicitudes, mostrar mensaje amigable
        if (!state.requests || state.requests.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center">No hay solicitudes para mostrar.</td></tr>';
            return;
        }

        // Renderizado seguro fila por fila
        let html = '';
        state.requests.forEach(req => {
            try {
                const dni = req.applicant?.dni || 'N/A';
                const name = `${req.applicant?.given_name || ''} ${req.applicant?.first_surname || ''}`.trim() || 'Desconocido';
                const status = req.status || 'unknown';
                const date = req.created_at ? new Date(req.created_at).toLocaleDateString() : 'N/A';
                
                html += `
                    <tr class="fade-in">
                        <td><strong>${dni}</strong></td>
                        <td>${name}</td>
                        <td><span class="status-badge status-${status}">${status.replace(/_/g, ' ')}</span></td>
                        <td>${date}</td>
                        <td>
                            <button class="nav-btn" onclick="ui.viewDetail('${req.request_id}')" title="Ver detalle">
                                <i data-lucide="eye" style="width:16px"></i>
                            </button>
                        </td>
                    </tr>
                `;
            } catch (err) {
                console.warn('Error renderizando fila:', err, req);
            }
        });

        tbody.innerHTML = html;
        
        // Reinicializar iconos si la librería Lucide está disponible
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    },
    updateStats() {
        const pending = state.requests.filter(r => r.status === 'pending_manual_review').length;
        const issued = state.requests.filter(r => r.status === 'issued').length;
        
        const pendingEl = document.getElementById('stat-pending');
        const issuedEl = document.getElementById('stat-issued');
        
        if (pendingEl) pendingEl.innerText = pending;
        if (issuedEl) issuedEl.innerText = issued;
    },
    async approveRequest(id, note) {
        ui.toast('Procesando aprobación...', 'info');
        try {
            const res = await fetch(`${API_BASE}/requests/${id}/approve`, {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'X-API-Key': RA_API_KEY
                },
                body: JSON.stringify({ note })
            });
            if (res.ok) {
                ui.toast('Solicitud aprobada y emitida', 'success');
                ui.closeModal();
                this.fetchRequests();
            } else {
                const data = await res.json();
                ui.toast(data.detail || 'Error al aprobar', 'danger');
            }
        } catch (err) {
            ui.toast('Error de conexión', 'danger');
        }
    },
    async rejectRequest(id, note) {
        ui.toast('Procesando rechazo...', 'info');
        try {
            const res = await fetch(`${API_BASE}/requests/${id}/reject`, {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'X-API-Key': RA_API_KEY
                },
                body: JSON.stringify({ note })
            });
            if (res.ok) {
                ui.toast('Solicitud rechazada', 'warning');
                ui.closeModal();
                this.fetchRequests();
            } else {
                const data = await res.json();
                ui.toast(data.detail || 'Error al rechazar', 'danger');
            }
        } catch (err) {
            ui.toast('Error de conexión', 'danger');
        }
    }
};

// --- UI Components / Views ---
const views = {
    home() {
        return `
            <div class="glass-card fade-in" style="text-align: center; max-width: 600px; margin: 4rem auto;">
                <div style="margin-bottom: 2rem;">
                    <i data-lucide="shield-check" style="width: 64px; height: 64px; color: var(--primary-color);"></i>
                </div>
                <h1>Emisión de Certificado Digital</h1>
                <p class="subtitle">Inicie su trámite de identidad digital de forma segura y remota.</p>
                <div style="display: flex; flex-direction: column; gap: 1rem;">
                    <button class="btn-primary" onclick="router.navigate('register')">
                        Comenzar Registro <i data-lucide="arrow-right"></i>
                    </button>
                    <p style="font-size: 0.8rem; color: var(--text-secondary);">
                        Requerirá su DNI físico y una cámara web activa.
                    </p>
                </div>
            </div>
        `;
    },
    register() {
        return `
            <div class="glass-card fade-in">
                <h2>Datos del Solicitante</h2>
                <div class="registration-stepper">
                    <div class="form-grid" style="display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem;">
                        <div class="form-group">
                            <label>DNI (8 dígitos)</label>
                            <input type="text" id="reg-dni" placeholder="Ej. 12345678" maxlength="8">
                        </div>
                        <div class="form-group">
                            <label>Correo Electrónico</label>
                            <input type="email" id="reg-email" placeholder="usuario@ejemplo.com">
                        </div>
                        <div class="form-group">
                            <label>Nombres</label>
                            <input type="text" id="reg-given-name">
                        </div>
                        <div class="form-group">
                            <label>Primer Apellido</label>
                            <input type="text" id="reg-first-surname">
                        </div>
                        <div class="form-group">
                            <label>Tipo de Certificado</label>
                            <select id="reg-profile">
                                <option value="Persona Natural">Persona Natural</option>
                                <option value="Persona Natural Representante Legal">Representante Legal</option>
                                <option value="Persona Natural Profesional">Profesional Independent</option>
                            </select>
                        </div>
                        <div class="form-group">
                            <label>Modalidad de Almacenamiento</label>
                            <select id="reg-mode">
                                <option value="local">Almacén Local (Token/PC)</option>
                                <option value="remote">Almacén Remoto (Nube/HSM)</option>
                            </select>
                        </div>
                    </div>
                           <div id="capture-section" style="margin-top: 2rem;">
                        <h3 id="capture-title">Paso Único: Captura de Selfie</h3>
                        <div id="capture-instruction" class="liveness-instruction-box" style="position: relative; top: 0; left: 0; transform: none; margin-bottom: 1rem; width: 100%;">
                            Centre su ROSTRO en el óvalo y mire a la cámara
                        </div>
                        
                        <div class="webcam-step" style="text-align:center">
                            <div class="webcam-container">
                                <video id="webcam" autoplay playsinline></video>
                                <div id="face-guide" class="capture-overlay" style="border-radius: 50% / 45%;"></div>
                                <!-- El overlay de liveness se inyectará aquí dinámicamente -->
                            </div>
                            
                            <div id="current-step-label" class="badge" style="margin-bottom: 1rem; padding: 5px 15px; display:none">DNI FRONT</div>
                            
                            <div style="display: flex; justify-content: center; gap: 1rem; margin-bottom: 1.5rem;">
                                <button id="btn-capture" class="btn-primary" onclick="webcam.capture()">
                                    <i data-lucide="camera"></i> Capturar Imagen
                                </button>
                                <button id="btn-mobile-sync" class="btn-primary" onclick="cryptoHelper.startMobileCapture()" style="background: var(--info); color: white;">
                                    <i data-lucide="smartphone"></i> Usar mi Celular
                                </button>
                            </div>
                            <canvas id="snapshot" width="640" height="480" style="display:none"></canvas>
                        </div>
                        
                        <div class="captured-gallery" style="display: flex; justify-content: center; gap: 1rem; margin: 1.5rem 0;">
                            <div class="thumb-item" style="text-align:center; width: 200px;">
                                <label style="font-size: 0.7rem; color: var(--text-secondary); display:block; margin-bottom:0.5rem">SELFIE DE IDENTIDAD</label>
                                <div id="thumb-selfie" style="background: rgba(0,0,0,0.3); border-radius: 4px; aspect-ratio:4/3; display:flex; align-items:center; justify-content:center; border: 1px dashed var(--border-color); font-size: 0.7rem; color: var(--text-secondary)">Vacío</div>
                            </div>
                        </div>
                    </div>

                    <div style="margin-top: 3rem; text-align: right;">
                        <button class="btn-primary" id="btn-submit-reg" onclick="registration.submit()" style="opacity:0.5" disabled>
                            Finalizar y Enviar Solicitud <i data-lucide="send"></i>
                        </button>
                    </div>
                </div>
            </div>
        `;
    },
    mobileCapture(sessionId) {
        return `
            <div class="glass-card fade-in" style="height: 90vh; display:flex; flex-direction:column; align-items:center; padding: 1rem; background: var(--bg-color);">
                <div style="text-align:center; margin-bottom: 1.5rem;">
                    <h2 style="color: var(--primary-color)">Validación Biométrica</h2>
                    <p style="font-size: 0.8rem; color: var(--text-secondary)">Complete los movimientos para habilitar la captura</p>
                </div>

                <!-- Cuadro de Instrucciones -->
                <div id="liveness-instruction-box" style="width: 100%; max-width: 320px; background: #1e293b; color: white; padding: 1rem; border-radius: 12px; text-align: center; margin-bottom: 1.5rem; border: 2px solid var(--info);">
                    <span id="liveness-status" style="font-weight: 700;">INICIANDO...</span>
                </div>

                <!-- Contenedor Único de Cámara con Óvalo Vertical -->
                <div style="position: relative; width: 280px; height: 380px; border-radius: 20px; overflow: hidden; border: 2px solid var(--border-color); background: #000;">
                    <video id="webcam-mobile" autoplay playsinline style="width: 100%; height: 100%; object-fit: cover;"></video>
                    <!-- Óvalo Vertical Perfecto -->
                    <div class="face-oval" style="position: absolute; top: 40px; left: 30px; width: 220px; height: 300px; border: 4px solid #00f2ff; border-radius: 50%; pointer-events: none; box-shadow: 0 0 15px rgba(0, 242, 255, 0.5);"></div>
                </div>

                <div style="margin-top: 2rem; width: 100%; max-width: 320px;">
                    <button id="btn-capture-mobile" class="btn-primary" style="width:100%; height: 65px; border-radius: 12px; font-size: 1.1rem; opacity: 0.5; background: #1e293b; color: #94a3b8; border: 1px solid #334155;" onclick="webcam.captureMobile('${sessionId}')" disabled>
                        BUSCANDO ROSTRO...
                    </button>
                    <p style="margin-top: 1.5rem; text-align: center;">
                        <a href="javascript:void(0)" onclick="webcam.forceEnableCapture()" style="color: var(--text-secondary); font-size: 0.8rem; text-decoration: underline;">¿No detecta tu rostro? Pulsar aquí para forzar captura</a>
                    </p>
                </div>
            </div>
        `;
    },
    dashboard() {
        return `
            <div class="fade-in">
                <div style="display:flex; justify-content: space-between; align-items: center; margin-bottom: 2rem;">
                    <h1>Panel de Control</h1>
                    <button class="nav-btn" onclick="api.fetchRequests()">
                        <i data-lucide="refresh-cw"></i> Actualizar
                    </button>
                </div>
                
                <div class="stats-grid">
                    <div class="stat-card">
                        <span class="stat-label">Pendientes</span>
                        <span class="stat-val" style="color: var(--warning)" id="stat-pending">-</span>
                    </div>
                    <div class="stat-card">
                        <span class="stat-label">Emitidos</span>
                        <span class="stat-val" style="color: var(--info)" id="stat-issued">-</span>
                    </div>
                </div>

                <div class="glass-card">
                    <h2>Solicitudes Recientes</h2>
                    <div class="table-responsive">
                        <table>
                            <thead>
                                <tr>
                                    <th>DNI</th>
                                    <th>Solicitante</th>
                                    <th>Estado</th>
                                    <th>Fecha</th>
                                    <th>Acción</th>
                                </tr>
                            </thead>
                            <tbody id="request-table-body">
                                <tr><td colspan="5" style="text-align:center">Cargando...</td></tr>
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        `;
    }
};

// --- Webcam Logic ---
const webcam = {
    stream: null,
    steps: ['selfie'],
    currentStep: 0,
    isLivenessActive: false,
    livenessState: 'idle', // 'idle', 'centering', 'detecting', 'completed'
    prevFrame: null,
    detectInterval: null,

    async init() {
        try {
            this.stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user', width: 640, height: 480 } });
            const video = document.getElementById('webcam');
            if (video) video.srcObject = this.stream;
        } catch (err) {
            ui.toast('No se pudo acceder a la cámara', 'danger');
        }
    },
    capture() {
        const stepName = this.steps[this.currentStep];
        this.takeSnapshot(stepName);
        this.currentStep++;
        this.updateUI();
    },
    takeSnapshot(stepName) {
        const video = document.getElementById('webcam');
        const canvas = document.getElementById('snapshot');
        const context = canvas.getContext('2d');
        context.drawImage(video, 0, 0, 640, 480);
        
        const blob = canvas.toDataURL('image/jpeg', 0.8);
        state.registration.images[stepName] = blob;

        const thumb = document.getElementById(`thumb-${stepName}`);
        if (thumb) thumb.innerHTML = `<img src="${blob}" style="width:100%; border-radius:4px; border: 1px solid var(--primary-color)">`;
    },
    updateUI() {
        const stepLabel = document.getElementById('current-step-label');
        const instruction = document.getElementById('capture-instruction');
        const title = document.getElementById('capture-title');
        const guide = document.getElementById('face-guide');
        
        if (this.currentStep < this.steps.length) {
            const stepName = this.steps[this.currentStep];
            if (stepLabel) stepLabel.innerText = stepName.replace('_', ' ').toUpperCase();
            
            // Actualizar instrucciones y guías visuales
            if (instruction) {
                if (stepName === 'dni_back') {
                    instruction.innerText = 'Coloque el REVERSO de su DNI dentro del recuadro';
                    if (title) title.innerText = 'Paso 2: Reverso de DNI';
                } else if (stepName === 'selfie') {
                    instruction.innerText = 'Centre su ROSTRO en el óvalo y mire a la cámara';
                    if (title) title.innerText = 'Paso 3: Selfie de Identidad';
                    if (guide) guide.style.borderRadius = '50% / 45%'; // Cambiar a Óvalo
                }
            }
        } else {
            const btn = document.getElementById('btn-capture');
            if (btn) btn.disabled = true;
            if (stepLabel) stepLabel.innerText = 'Captura Completa';
            if (instruction) instruction.innerText = '¡Todo listo! Ya puede enviar su solicitud.';
            if (title) title.innerText = 'Finalizado';
            
            const submitBtn = document.getElementById('btn-submit-reg');
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.style.opacity = '1';
            }
        }
    },
    startAutomaticLiveness() {
        this.isLivenessActive = true;
        this.livenessState = 'centering';
        
        const instruction = document.getElementById('capture-instruction');
        const title = document.getElementById('capture-title');
        const guide = document.getElementById('face-guide');
        
        if (title) title.innerText = 'Paso 4: Prueba de Vida Activa';
        if (instruction) instruction.innerText = 'Centre su rostro en el óvalo';
        if (guide) guide.style.display = 'none'; // Ocultamos la guía estática

        // Crear elementos UI de liveness
        const container = document.querySelector('.webcam-container');
        container.insertAdjacentHTML('beforeend', `
            <div id="liveness-ui" class="fade-in">
                <div class="face-mask-container"><div class="face-oval" id="liveness-oval"></div></div>
                <div class="liveness-progress"><div class="liveness-progress-fill" id="liveness-pb"></div></div>
            </div>
        `);
        
        document.getElementById('btn-capture').style.display = 'none';
        
        // Loop de detección (10 fps)
        this.prevFrame = null;
        let stabilityCounter = 0;
        let movementDetected = false;
        let progress = 0;

        this.detectInterval = setInterval(() => {
            const video = document.getElementById('webcam');
            if (!video) return;

            const diff = this.computeFrameDifference(video);
            const pb = document.getElementById('liveness-pb');
            const msg = document.getElementById('liveness-msg');
            const oval = document.getElementById('liveness-oval');

            if (this.livenessState === 'centering') {
                oval.className = 'face-oval detecting';
                if (diff < 12000) { // Umbral de estabilidad calibrado para camaras con ruido
                    stabilityCounter++;
                    progress = (stabilityCounter / 15) * 100;
                    if (pb) pb.style.width = `${progress}%`;
                    
                    if (stabilityCounter > 15) {
                        this.livenessState = 'detecting';
                        stabilityCounter = 0;
                        if (msg) msg.innerText = '¡Gire la cabeza a la derecha ahora!';
                        if (pb) pb.style.width = '0%';
                        if (pb) pb.style.backgroundColor = 'var(--warning)';
                    }
                } else {
                    stabilityCounter = 0;
                    if (pb) pb.style.width = '0%';
                }
            } else if (this.livenessState === 'detecting') {
                oval.className = 'face-oval success';
                if (diff > 40000) { // Umbral de movimiento calibrado
                    this.takeSnapshot('liveness');
                    this.currentStep++;
                    this.livenessState = 'completed';
                    if (msg) msg.innerText = '¡Captura Exitosa!';
                    if (pb) pb.style.width = '100%';
                    if (pb) pb.style.backgroundColor = 'var(--success)';
                    
                    setTimeout(() => this.stopLiveness(), 1500);
                }
            }
        }, 100);
    },
    computeFrameDifference(video) {
        // Usar un canvas miniatura para comparar píxeles
        const canvas = document.createElement('canvas');
        canvas.width = 48;
        canvas.height = 48;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(video, 0, 0, 48, 48);
        const currentFrame = ctx.getImageData(0, 0, 48, 48).data;

        if (!this.prevFrame) {
            this.prevFrame = currentFrame;
            return 0;
        }

        let totalDiff = 0;
        for (let i = 0; i < currentFrame.length; i += 4) {
            totalDiff += Math.abs(currentFrame[i] - this.prevFrame[i]);
        }
        
        this.prevFrame = currentFrame;
        return totalDiff;
    },
    stopLiveness() {
        clearInterval(this.detectInterval);
        this.isLivenessActive = false;
        const ui = document.getElementById('liveness-ui');
        if (ui) ui.remove();
        
        this.updateUI();
    },
    stop() {
        this.stopLiveness();
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
        }
    },
    async initMobile(sessionId) {
        try {
            ui.toast('Cargando motor de IA (FaceAPI)...', 'info');
            
            // Cargar modelos mínimos necesarios desde CDN (más ligero)
            const MODEL_URL = 'https://justadudewhohacks.github.io/face-api.js/models';
            await Promise.all([
                faceapi.nets.ssdMobilenetv1.loadFromUri(MODEL_URL),
                faceapi.nets.faceLandmark68Net.loadFromUri(MODEL_URL)
            ]);
            
            ui.toast('Iniciando cámara...', 'info');
            this.stream = await navigator.mediaDevices.getUserMedia({ 
                video: { 
                    facingMode: 'user',
                    width: { ideal: 640 },
                    height: { ideal: 480 }
                } 
            });
            
            const video = document.getElementById('webcam-mobile');
            if (video) {
                video.srcObject = this.stream;
                video.onloadedmetadata = () => {
                    this.startFaceDetection(video);
                };
            }
        } catch (err) {
            console.error('Mobile WebCam Error:', err);
            ui.toast('Error al iniciar cámara: ' + err.message, 'danger');
        }
    },
    startFaceDetection(video) {
        const btn = document.getElementById('btn-capture-mobile');
        const oval = document.querySelector('.face-oval');
        const statusEl = document.getElementById('liveness-status');
        const boxEl = document.getElementById('liveness-instruction-box');
        
        if (statusEl) statusEl.innerText = '🔍 BUSCANDO ROSTRO...';
        
        const detect = async () => {
            if (!video || !this.isMobileActive) return;
            
            try {
                // Validación de rostro simplificada con FaceAPI
                const detection = await faceapi.detectSingleFace(video, new faceapi.SsdMobilenetv1Options({ minConfidence: 0.5 }));
                
                if (detection) {
                    if (statusEl) statusEl.innerText = '✅ ROSTRO DETECTADO';
                    if (boxEl) boxEl.style.background = 'var(--success)';
                    if (oval) {
                        oval.style.borderColor = 'var(--success)';
                        oval.style.opacity = '1';
                    }

                    if (btn && btn.disabled) {
                        btn.disabled = false;
                        btn.style.opacity = '1';
                        btn.style.background = 'var(--primary-color)';
                        btn.style.color = 'white';
                        btn.innerHTML = '<span>📸 TOMAR FOTO AHORA</span>';
                    }
                } else {
                    if (statusEl && statusEl.innerText !== '⚠️ MODO MANUAL ACTIVADO') {
                        if (statusEl) statusEl.innerText = '🔍 BUSCANDO ROSTRO...';
                        if (boxEl) boxEl.style.background = 'var(--danger)';
                        if (oval) {
                            oval.style.borderColor = 'var(--primary-color)';
                            oval.style.opacity = '0.5';
                        }
                    }
                }
            } catch (err) {
                console.error("Error en detección:", err);
            }
            
            if (this.isMobileActive) {
                setTimeout(() => requestAnimationFrame(detect), 200); // 5 FPS para ahorrar batería
            }
        };
        
        detect();
        this.isMobileActive = true;
    },
    async captureMobile(sessionId) {
        const video = document.getElementById('webcam-mobile');
        const canvas = document.createElement('canvas');
        canvas.width = 640;
        canvas.height = 640;
        const ctx = canvas.getContext('2d');
        
        // Captura cuadrada centrada
        const size = Math.min(video.videoWidth, video.videoHeight);
        const x = (video.videoWidth - size) / 2;
        const y = (video.videoHeight - size) / 2;
        ctx.drawImage(video, x, y, size, size, 0, 0, 640, 640);
        
        const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.8));
        const formData = new FormData();
        formData.append('selfie_image', blob, 'mobile_selfie.jpg');
        
        const btn = document.getElementById('btn-capture-mobile');
        btn.disabled = true;
        btn.innerText = 'Subiendo...';
        
        try {
            const res = await fetch(`${API_BASE}/sessions/${sessionId}/upload`, {
                method: 'POST',
                body: formData
            });
            if (res.ok) {
                const badge = document.getElementById('liveness-status');
                if (badge) {
                    badge.innerText = '✅ ¡FOTO ENVIADA!';
                    badge.parentElement.style.background = 'var(--success)';
                }
                btn.style.display = 'none';
                this.stop();
            } else {
                throw new Error('Error al subir');
            }
        } catch (err) {
            ui.toast('Error al enviar la foto', 'danger');
            btn.disabled = false;
            btn.innerText = 'Reintentar Captura';
        }
    },
    forceEnableCapture() {
        const btn = document.getElementById('btn-capture-mobile');
        const statusEl = document.getElementById('liveness-status');
        const boxEl = document.getElementById('liveness-instruction-box');
        
        if (btn) {
            btn.disabled = false;
            btn.style.opacity = '1';
            btn.style.background = 'var(--warning)';
            btn.style.color = 'black';
            btn.innerHTML = '<span>📸 TOMAR FOTO AHORA (FORZADO)</span>';
        }
        if (statusEl) statusEl.innerText = '⚠️ MODO MANUAL ACTIVADO';
        if (boxEl) boxEl.style.background = 'var(--warning)';
        
        ui.toast('Modo manual activado. Tome su foto ahora.', 'warning');
    }
};

// --- Cryptography Helper (Real CSR) ---
const cryptoHelper = {
    async generateCSR(data) {
        ui.toast('Generando llaves RSA y CSR...', 'info');
        return new Promise((resolve, reject) => {
            // Pequeño timeout para dejar que la UI respire antes del proceso pesado
            setTimeout(() => {
                try {
                    if (typeof forge === 'undefined') {
                        throw new Error('La librería criptográfica (Forge) no se ha cargado.');
                    }

                    // Generar par de llaves RSA 2048
                    const keys = forge.pki.rsa.generateKeyPair(2048);
                    const csr = forge.pki.createCertificationRequest();
                    csr.publicKey = keys.publicKey;
                    
                    // Construir Subject exigido por la RA/EC (CN = Nombre Completo, serialNumber = DNI)
                    const fullName = `${data.given_name} ${data.first_surname}`.toUpperCase();
                    csr.setSubject([
                        { name: 'commonName', value: fullName },
                        { name: 'serialNumber', value: data.dni },
                        { name: 'countryName', value: 'PE' },
                        { name: 'emailAddress', value: data.email },
                        { name: 'organizationalUnitName', value: data.certificate_profile }
                    ]);

                    // Firmar CSR con la llave privada
                    csr.sign(keys.privateKey);

                    // Convertir a PEM
                    const csrPem = forge.pki.certificationRequestToPem(csr);
                    const privateKeyPem = forge.pki.privateKeyToPem(keys.privateKey);

                    // Guardar llave privada en el navegador para que el usuario no la pierda
                    try {
                        localStorage.setItem(`private_key_${data.dni}`, privateKeyPem);
                    } catch (storageErr) {
                        console.warn('No se pudo guardar la llave en localStorage:', storageErr);
                        // No rechazamos por esto, el usuario podrá descargarla al final
                    }
                    
                    resolve(csrPem);
                } catch (err) {
                    console.error('Crypto Error Detail:', err);
                    reject(err);
                }
            }, 100);
        });
    },
    downloadPrivateKey(dni) {
        const key = localStorage.getItem(`private_key_${dni}`);
        if (!key) return;
        const blob = new Blob([key], {type: 'text/plain'});
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `llave_privada_${dni}.key`;
        a.click();
    },
    async startMobileCapture() {
        try {
            ui.toast('Iniciando sesión segura...', 'info');
            const res = await fetch(`${API_BASE}/sessions`, { method: 'POST' });
            if (!res.ok) throw new Error('No se pudo crear la sesión');
            
            const session = await res.json();
            // Use current origin for the capture URL
            let captureUrl = `${window.location.origin}${window.location.pathname}?session=${session.session_id}`;
            
            // If on localhost, we might want to warn the user or provide a LAN IP, 
            // but with Cloudflare Tunnel, window.location.origin will already be the public URL.
            console.log("Mobile Capture URL:", captureUrl);
            
            // Mostrar modal con QR
            ui.showQRModule(captureUrl, session.session_id);
            
            // Iniciar polling
            this.startPolling(session.session_id);
        } catch (err) {
            ui.toast('Error al iniciar captura móvil', 'danger');
        }
    },
    async startPolling(sessionId) {
        // Clear any existing polling before starting a new one
        if (state.activePolling) {
            clearInterval(state.activePolling);
            state.activePolling = null;
        }

        const interval = setInterval(async () => {
            try {
                const res = await fetch(`${API_BASE}/sessions/${sessionId}`);
                if (!res.ok) {
                    if (res.status === 410) {
                        ui.toast('La sesión móvil ha expirado', 'warning');
                        clearInterval(interval);
                    }
                    return;
                }
                
                const data = await res.json();
                console.log('Polling session status:', data.status, 'Has image:', !!data.selfie_b64);
                
                if (data.status === 'completed') {
                    if (data.selfie_b64) {
                        console.log('Selfie received! Updating UI...');
                        clearInterval(interval);
                        
                        // Actualizar estado local
                        state.registration.images.selfie = `data:image/jpeg;base64,${data.selfie_b64}`;
                        
                        // Asegurarnos de cerrar el modal
                        ui.closeModal();
                        
                        // Buscar el contenedor de la miniatura en el DOM
                        const thumb = document.getElementById('thumb-selfie');
                        if (thumb) {
                            thumb.innerHTML = `<img src="${state.registration.images.selfie}" style="width:100%; border-radius:4px; border: 3px solid var(--success); box-shadow: 0 0 15px var(--success-glow);">`;
                        }
                        
                        ui.toast('¡Excelente! Selfie recibida con éxito.', 'success');
                        
                        // Habilitar el botón final de registro
                        const submitBtn = document.getElementById('btn-submit-reg');
                        if (submitBtn) {
                            submitBtn.disabled = false;
                            submitBtn.style.opacity = '1';
                            submitBtn.classList.add('pulse-animation');
                        }
                    } else {
                        console.warn('Status is completed but no image yet, retrying...');
                    }
                }
            } catch (err) {
                console.warn('Polling error:', err);
            }
        }, 2000);
        
        // Guardamos el interval en algún lugar por si hay que cancelarlo
        state.activePolling = interval;
    }
};

// --- Registration Process ---
const registration = {
    async submit() {
        const formData = new FormData();
        const dni = document.getElementById('reg-dni').value;
        const given_name = document.getElementById('reg-given-name').value;
        const first_surname = document.getElementById('reg-first-surname').value;
        const email = document.getElementById('reg-email').value;
        const profile = document.getElementById('reg-profile').value;
        const mode = document.getElementById('reg-mode').value;

        if (!dni || !given_name || !first_surname || !email) {
            return ui.toast('Todos los campos son obligatorios', 'warning');
        }

        if (dni.length !== 8 || isNaN(dni)) {
            return ui.toast('El DNI debe tener exactamente 8 números.', 'danger');
        }

        try {
            // 1. Generar CSR solo si es modo LOCAL
            let csrPem = null;
            if (mode === 'local') {
                try {
                    csrPem = await cryptoHelper.generateCSR({ dni, given_name, first_surname, email, certificate_profile: profile });
                } catch (cryptoErr) {
                    throw new Error('ERROR_CRYPTO: ' + cryptoErr.message);
                }
            }
            
            formData.append('dni', dni);
            formData.append('given_name', given_name);
            formData.append('first_surname', first_surname);
            formData.append('email', email);
            formData.append('certificate_profile', profile);
            formData.append('issuance_mode', mode);
            if (csrPem) formData.append('csr_pem', csrPem);
            formData.append('consent_text', 'Acepto los términos y condiciones de la entidad.');

            // Si hay sesión móvil activa, enviamos info de captura si fuera necesario, 
            // pero las imágenes ya están en state.registration.images gracias al polling.
            
            // Convert base64 images to Files
            const images = state.registration.images;
            if (images.dni_front) formData.append('dni_front_image', this.dataURLtoFile(images.dni_front, 'front.jpg'));
            if (images.dni_back) formData.append('dni_back_image', this.dataURLtoFile(images.dni_back, 'back.jpg'));
            if (images.selfie) formData.append('selfie_image', this.dataURLtoFile(images.selfie, 'selfie.jpg'));
            if (images.liveness) formData.append('liveness_image', this.dataURLtoFile(images.liveness, 'liveness.jpg'));

            ui.toast('Enviando solicitud segura...', 'info');
            
            let res;
            try {
                res = await fetch(`${API_BASE}/requests/multipart`, {
                    method: 'POST',
                    body: formData
                });
            } catch (netErr) {
                throw new Error('ERROR_NETWORK: No se pudo conectar con el servidor.');
            }

            if (res.ok) {
                const data = await res.json();
                ui.success(data.request_id, dni, mode);
            } else {
                let detail = 'Error desconocido en el servidor';
                try {
                    const errData = await res.json();
                    detail = errData.detail || detail;
                } catch (jsonErr) {
                    detail = `Error del Servidor (${res.status})`;
                }
                ui.toast(detail, 'danger');
            }
        } catch (err) {
            console.error('Submit Error:', err);
            if (err.message.startsWith('ERROR_CRYPTO')) {
                ui.toast('Error en el proceso criptográfico: ' + err.message.replace('ERROR_CRYPTO: ', ''), 'danger');
            } else if (err.message.startsWith('ERROR_NETWORK')) {
                ui.toast(err.message.replace('ERROR_NETWORK: ', ''), 'danger');
            } else {
                ui.toast('Error inesperado: ' + err.message, 'danger');
            }
        }
    },
    dataURLtoFile(dataurl, filename) {
        var arr = dataurl.split(','), mime = arr[0].match(/:(.*?);/)[1],
            bstr = atob(arr[1]), n = bstr.length, u8arr = new Uint8Array(n);
        while(n--){
            u8arr[n] = bstr.charCodeAt(n);
        }
        return new File([u8arr], filename, {type:mime});
    }
};

// --- UI Utilities ---
const ui = {
    toast(msg, type = 'info') {
        const t = document.createElement('div');
        t.className = `stat-card fade-in`;
        t.style = `position:fixed; bottom:20px; right:20px; z-index:2000; border-left: 4px solid var(--${type}); min-width: 250px; background: var(--surface-glass); backdrop-filter:blur(10px);`;
        t.innerHTML = `<strong>${type.toUpperCase()}</strong><br>${msg}`;
        document.getElementById('toast-container').appendChild(t);
        setTimeout(() => t.remove(), 4000);
    },
    success(id, dni, mode) {
        const isRemote = mode === 'remote';
        
        const keySection = isRemote ? `
            <div class="stat-card" style="margin-bottom: 2rem; border-left: 4px solid var(--info);">
                <p style="font-weight: 600; color: var(--info); margin-bottom: 0.5rem;">ALMACENAMIENTO CENTRALIZADO (HSM)</p>
                <p style="font-size: 0.85rem; color: var(--text-secondary);">
                    Al elegir el modo remoto, su <strong>Llave Privada será generada por el HSM de la EC</strong> una vez que su solicitud sea aprobada.
                    Esto garantiza que su llave nunca salga del entorno seguro del HSM. No requiere descargar ningún archivo.
                </p>
            </div>
        ` : `
            <div class="stat-card" style="margin-bottom: 2rem; border-left: 4px solid var(--warning);">
                <p style="font-weight: 600; color: var(--warning); margin-bottom: 0.5rem;">¡ACCIÓN REQUERIDA!</p>
                <p style="font-size: 0.85rem; color: var(--text-secondary);">
                    Se ha generado una <strong>Llave Privada</strong> única en su navegador. 
                    <strong>Es obligatorio descargarla AHORA</strong>. Una vez que el operador apruebe su solicitud, usará esta llave para activar su certificado.
                </p>
                <button class="btn-primary" onclick="cryptoHelper.downloadPrivateKey('${dni}')" style="margin-top: 1rem; background: var(--warning); color: black;">
                    <i data-lucide="key"></i> Descargar Llave Privada (.key)
                </button>
            </div>
        `;

        document.getElementById('view-container').innerHTML = `
            <div class="glass-card fade-in" style="text-align: center; max-width: 600px; margin: 4rem auto;">
                <i data-lucide="check-circle" style="width: 64px; height: 64px; color: var(--success); margin-bottom:1rem"></i>
                <h1>Solicitud Enviada</h1>
                <p>Su trámite ha sido registrado con éxito.</p>
                <div style="background: rgba(0,0,0,0.2); padding: 1.5rem; border-radius: 12px; margin: 1.5rem 0; border: 1px solid var(--border-color);">
                    <p style="font-size: 0.8rem; color: var(--text-secondary); margin-bottom: 0.5rem;">ID DE TRAMITE</p>
                    <code style="color: var(--primary-color); font-size: 1.2rem; font-weight: 700;">${id}</code>
                </div>

                ${keySection}

                <button class="btn-primary" onclick="router.navigate('home')">Volver al Inicio</button>
            </div>
        `;
        lucide.createIcons();
    },
    viewDetail(id) {
        const req = state.requests.find(r => r.request_id === id);
        if (!req) return;

        const modal = document.getElementById('modal-overlay');
        const content = document.getElementById('modal-content');
        
        content.innerHTML = `
            <div style="display:flex; justify-content: space-between; align-items: center; margin-bottom: 2rem;">
                <h2>Detalle del Trámite</h2>
                <button class="nav-btn" onclick="ui.closeModal()"><i data-lucide="x"></i></button>
            </div>
            <div class="evidence-grid">
                <div class="evidence-item">
                    <p style="font-size:0.8rem; color:var(--text-secondary)">DNI FRONT</p>
                    <img class="evidence-img" src="${API_BASE}/requests/${id}/evidence/dni_front?X-API-Key=${RA_API_KEY}">
                </div>
                <div class="evidence-item">
                    <p style="font-size:0.8rem; color:var(--text-secondary)">SELFIE</p>
                    <img class="evidence-img" src="${API_BASE}/requests/${id}/evidence/selfie?X-API-Key=${RA_API_KEY}">
                </div>
            </div>
            <div class="stat-card" style="margin-bottom: 1.5rem;">
                <p><strong>Solicitante:</strong> ${req.applicant.given_name} ${req.applicant.first_surname}</p>
                <p><strong>DNI:</strong> ${req.applicant.dni}</p>
                <p><strong>Modalidad:</strong> <span class="badge" style="background:var(--primary-glow)">${(req.applicant.issuance_mode || 'local').toUpperCase()}</span></p>
                <p><strong>Estado Actual:</strong> <span class="status-badge status-${req.status}">${req.status.replace(/_/g, ' ')}</span></p>
                <p><strong>Similitud Biometria:</strong> <span style="color:var(--success)">${(req.reniec_result.similarity_score * 100).toFixed(2)}%</span></p>
            </div>
            <div class="form-group">
                <label>Nota de Revisión</label>
                <textarea id="review-note" placeholder="Escriba el motivo de la aprobación o rechazo..."></textarea>
            </div>
            <div style="display:flex; gap: 1rem; justify-content: flex-end;">
                <button class="btn-primary" style="background:var(--danger)" onclick="api.rejectRequest('${id}', document.getElementById('review-note').value)">Rechazar</button>
                <button class="btn-primary" onclick="api.approveRequest('${id}', document.getElementById('review-note').value)">Aprobar y Emitir</button>
            </div>
        `;
        modal.classList.remove('hidden');
        lucide.createIcons();
    },
    closeModal() {
        if (state.activePolling) {
            clearInterval(state.activePolling);
            state.activePolling = null;
        }
        document.getElementById('modal-overlay').classList.add('hidden');
    },
    showQRModule(url, sessionId) {
        const modal = document.getElementById('modal-overlay');
        const content = document.getElementById('modal-content');
        
        content.innerHTML = `
            <div style="text-align:center; padding: 1rem;">
                <h2 style="margin-bottom: 0.5rem;">Vincular Celular</h2>
                <p style="font-size: 0.85rem; color: var(--text-secondary); margin-bottom: 1.5rem;">
                    Escanee este código con su celular para tomar la selfie con su cámara móvil.
                </p>
                
                <div id="qrcode" style="display: flex; justify-content: center; background: white; padding: 1rem; border-radius: 12px; margin-bottom: 1.5rem;"></div>
                
                <div class="stat-card" style="border-left: 4px solid var(--info); text-align: left; font-size: 0.8rem;">
                    <strong>Instrucciones:</strong><br>
                    1. Abra la cámara de su móvil.<br>
                    2. Escanee el código y abra el enlace.<br>
                    3. No cierre esta ventana en su PC.
                </div>
                
                <button class="btn-primary" onclick="ui.closeModal()" style="margin-top: 1.5rem; background: transparent; color: var(--text-secondary); border: 1px solid var(--border-color);">
                    Cancelar sincronización
                </button>
            </div>
        `;
        
        modal.classList.remove('hidden');
        new QRCode(document.getElementById("qrcode"), {
            text: url,
            width: 200,
            height: 200,
            colorDark : "#000000",
            colorLight : "#ffffff",
            correctLevel : QRCode.CorrectLevel.H
        });
    }
};

// --- Initialization ---
document.addEventListener('DOMContentLoaded', () => {
    router.render();
    
    // Auto-init webcam if on registration view
    window.addEventListener('click', (e) => {
        if (e.target.id === 'btn-start-reg' || state.currentView === 'register') {
            setTimeout(() => webcam.init(), 100);
        }
    });

    // Handle view specific logic
    const originalNavigate = router.navigate.bind(router);
    router.navigate = (view) => {
        webcam.stop();
        originalNavigate(view);
        if (view === 'register') {
            setTimeout(() => webcam.init(), 100);
        }
    };
});
