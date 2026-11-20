// The browser camera, kept in one place so the selfie step can be tested without a real camera.

export const CAMERA_UNSUPPORTED = 'unsupported'
export const CAMERA_INSECURE = 'insecure'
export const CAMERA_DENIED = 'denied'
export const CAMERA_MISSING = 'missing'

// Opens the front camera. Rejects with an Error whose `reason` is one of the constants above.
export async function openCamera() {
  const fail = (reason) => Object.assign(new Error(reason), { reason })
  if (!window.isSecureContext) throw fail(CAMERA_INSECURE)
  if (!navigator.mediaDevices?.getUserMedia) throw fail(CAMERA_UNSUPPORTED)
  try {
    return await navigator.mediaDevices.getUserMedia({
      audio: false,
      video: { facingMode: 'user', width: { ideal: 1280 }, height: { ideal: 960 } },
    })
  } catch (error) {
    if (error?.name === 'NotAllowedError' || error?.name === 'SecurityError') throw fail(CAMERA_DENIED)
    throw fail(CAMERA_MISSING)
  }
}

export function stopCamera(stream) {
  stream?.getTracks().forEach((track) => track.stop())
}

// The current video frame as a JPEG. Not mirrored, so the photo shows the person as others see them.
export function captureFrame(video) {
  const canvas = document.createElement('canvas')
  canvas.width = video.videoWidth
  canvas.height = video.videoHeight
  canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height)
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error('capture failed'))), 'image/jpeg', 0.92)
  })
}
