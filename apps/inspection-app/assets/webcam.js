getImageFromCamera = () => {
    const canvas = document.getElementById("canvas");
    const ctx = canvas.getContext("2d");
    const video = document.getElementById("video");

    canvas.width = 512;
    canvas.height = 512;

    // Get video dimensions
    const videoWidth = video.videoWidth;
    const videoHeight = video.videoHeight;

    // Calculate the largest centered square in the video
    const side = Math.min(videoWidth, videoHeight);
    const sx = (videoWidth - side) / 2;
    const sy = (videoHeight - side) / 2;

    // Draw the center-cropped square to the canvas, scaling to fit
    ctx.drawImage(video, sx, sy, side, side, 0, 0, canvas.width, canvas.height);

    const imageData = canvas.toDataURL("image/jpeg");
    return imageData;
};

sendImageToServer = (imageData) => {
    fetch("/capture-frame", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ image: imageData })
        })
        .then(res => {
            console.log("Received response");
            return res.json();
        })
        .then(data => {
            console.log("Server response data:", data);
            document.getElementById("captured-image").src = imageData;
        })
        .catch(err => {
            console.error("Error during fetch/upload:", err);
        });
};

insertWebcam = () => {
    console.log("insertWebcam called");

    var container = document.getElementById("video-container");
    if (!container) {
        console.error("video-container element not found");
        return;
    }
    container.innerHTML = `
        <div class="video-wrapper">
            <video id="video" autoplay playsinline class="video-element"></video>
            <div id="action-overlay" class="action-overlay"></div>
        </div>
        <canvas id="canvas" width="1280" height="720" class="canvas-hidden"></canvas>
    `;

    const video = document.getElementById("video");

    // Reusable overlay function
    const showOverlay = (message, overlayClass, duration = 1000) => {
        const overlay = document.getElementById("action-overlay");
        overlay.textContent = message;
        overlay.className = `action-overlay ${overlayClass}`;
        overlay.style.display = "flex";
        
        setTimeout(() => {
            overlay.style.display = "none";
        }, duration);
    };

    navigator.mediaDevices.getUserMedia({ video: true })
        .then(stream => {
            console.log("Webcam stream started");
            video.srcObject = stream;
        })
        .catch(err => {
            console.error("Error accessing webcam:", err);
        });

    document.getElementById("capture-btn").addEventListener("click", () => {
        console.log("Capture button clicked");
        
        showOverlay("📸 Capturing...", "overlay-capture", 500);
        
        const imageData = getImageFromCamera();
        console.log("Image captured from video, sending to server...");

        sendImageToServer(imageData);
    });

    // Add validate button event listener
    document.getElementById("validate-btn").addEventListener("click", () => {
        console.log("Validate button clicked");
        showOverlay("✅ Validating...", "overlay-validate");
        
        const imageData = getImageFromCamera();
        console.log("Image captured from video, sending to server for validation...");
        sendImageToServer(imageData);
    });

    // Add classify button event listener
    document.getElementById("classify-btn").addEventListener("click", () => {
        console.log("Classify button clicked");
        showOverlay("🔍 Classifying...", "overlay-classify");
        const imageData = getImageFromCamera();
        console.log("Image captured from video, sending to server for classification...");
        sendImageToServer(imageData);
    });

    // Add normal data button event listener
    document.getElementById("normal-data-btn").addEventListener("click", () =>
    {
        console.log("Normal data button clicked");
        showOverlay("📊 Submitting normal data...", "overlay-submit-data");
    });
    
    // Add anomaly data button event listener
    document.getElementById("anomaly-data-btn").addEventListener("click", () => {
        console.log("Anomaly data button clicked");     
        showOverlay("⚠️ Submitting anomaly data...", "overlay-submit-data");
    });
};

window.addEventListener('DOMContentLoaded', () => {
    console.log("DOM fully loaded and parsed");
    // wait before initializing webcam
    setTimeout(insertWebcam, 2000);
});
