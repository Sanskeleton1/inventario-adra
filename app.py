import { initializeApp } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-app.js";
import { getAuth, signInWithPopup, GoogleAuthProvider } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-auth.js";
import { getFirestore, doc, getDoc, setDoc } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-firestore.js";

// Reemplaza esto con la configuración de tu proyecto Firebase
const firebaseConfig = {
  apiKey: "TU_API_KEY",
  authDomain: "tu-proyecto.firebaseapp.com",
  projectId: "tu-proyecto",
  storageBucket: "tu-proyecto.appspot.com",
  messagingSenderId: "TUS_DATOS",
  appId: "TUS_DATOS"
};

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const db = getFirestore(app);
const provider = new GoogleAuthProvider();

const btnGoogle = document.getElementById('btn-google');
const statusMessage = document.getElementById('status-message');
const loginSection = document.getElementById('login-section');
const messageSection = document.getElementById('message-section');

btnGoogle.addEventListener('click', async () => {
    try {
        const result = await signInWithPopup(auth, provider);
        const user = result.user;
        
        // Referencia al documento del usuario en Firestore
        const userRef = doc(db, "usuarios", user.uid);
        const userSnap = await getDoc(userRef);

        loginSection.style.display = 'none';
        messageSection.style.display = 'block';

        if (userSnap.exists()) {
            // El usuario ya existe, revisamos su estado
            const userData = userSnap.data();
            if (userData.estado === "aprobado") {
                statusMessage.innerText = "¡Acceso concedido! Redirigiendo al sistema...";
                // window.location.href = "dashboard.html"; // Redirigir a la página de trabajo
            } else {
                statusMessage.innerText = "Tu cuenta sigue en revisión por el administrador.";
                auth.signOut(); // Cerramos su sesión por seguridad hasta que se apruebe
            }
        } else {
            // Es la primera vez que entra, lo registramos como pendiente
            await setDoc(userRef, {
                nombre: user.displayName,
                email: user.email,
                estado: "pendiente",
                fechaRegistro: new Date()
            });
            statusMessage.innerText = "Registro exitoso. Se ha enviado una solicitud a administración. Te notificaremos cuando seas aprobado.";
            auth.signOut();
        }
    } catch (error) {
        console.error("Error en la autenticación:", error);
        alert("Hubo un error al iniciar sesión.");
    }
});
