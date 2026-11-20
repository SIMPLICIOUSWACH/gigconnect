import { useEffect, useId, useRef, useState } from 'react'
import { fetchSelfieChallenge, submitSelfie } from '../../api/profile'
import {
  CAMERA_DENIED,
  CAMERA_INSECURE,
  CAMERA_MISSING,
  CAMERA_UNSUPPORTED,
  captureFrame,
  openCamera,
  stopCamera,
} from './camera'

const CAMERA_MESSAGES = {
  [CAMERA_DENIED]: "We couldn't use your camera because permission was turned down.",
  [CAMERA_MISSING]: "We couldn't find a camera on this device.",
  [CAMERA_UNSUPPORTED]: "This browser can't use a camera.",
  [CAMERA_INSECURE]: 'The camera only works on a secure (https) address.',
}

const primary =
  'min-h-[48px] px-5 rounded-button bg-primary text-white text-[15px] font-bold hover:bg-primary-hover disabled:bg-disabled disabled:text-muted disabled:cursor-not-allowed'
const secondary =
  'min-h-[48px] px-5 rounded-button border-2 border-ink text-ink text-[15px] font-bold hover:bg-sand disabled:opacity-50'

function timeOf(value) {
  return new Date(value).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit' })
}

// The "Take a selfie" step: the consent, a random challenge, the camera with an oval guide, then Retake or Use photo.
// Camera only: there is no file picker.
export default function SelfieCapture({ onDone }) {
  const [stage, setStage] = useState('start') // start | consent | camera | preview | sending
  const [challenge, setChallenge] = useState(null)
  const [consent, setConsent] = useState(false)
  const [cameraProblem, setCameraProblem] = useState('')
  const [photo, setPhoto] = useState(null) // { blob, url }
  const [message, setMessage] = useState('')
  const video = useRef(null)
  const stream = useRef(null)
  const consentId = useId()

  useEffect(() => () => stopCamera(stream.current), [])
  useEffect(() => () => photo && URL.revokeObjectURL(photo.url), [photo])

  // The note is shown with the new challenge, for example to say why the last one stopped working.
  const newChallenge = async (note = '') => {
    setMessage(note)
    try {
      setChallenge(await fetchSelfieChallenge())
      setStage('consent')
    } catch {
      setMessage('We could not start the selfie step. Try again in a moment.')
    }
  }

  const startCamera = async () => {
    setCameraProblem('')
    setMessage('')
    try {
      stream.current = await openCamera()
      setStage('camera')
    } catch (error) {
      setCameraProblem(error.reason || CAMERA_MISSING)
    }
  }

  // Attach the stream once the <video> is on the page.
  useEffect(() => {
    if (stage === 'camera' && video.current && stream.current) {
      video.current.srcObject = stream.current
      video.current.play?.().catch(() => {})
    }
  }, [stage])

  const takePhoto = async () => {
    try {
      const blob = await captureFrame(video.current)
      stopCamera(stream.current)
      stream.current = null
      setPhoto({ blob, url: URL.createObjectURL(blob) })
      setStage('preview')
    } catch {
      setMessage('That did not work. Try taking the photo again.')
    }
  }

  const retake = () => {
    setPhoto(null)
    startCamera()
  }

  const usePhoto = async () => {
    setStage('sending')
    setMessage('')
    try {
      await submitSelfie({ selfie: photo.blob, challengeId: challenge.id, consent })
      onDone?.()
    } catch (error) {
      const data = error.response?.data || {}
      if (data.code === 'challenge_expired') {
        setPhoto(null)
        await newChallenge('That challenge expired. Here is a new one: read it, then take the photo again.')
        return
      }
      setMessage(data.selfie?.[0] || data.consent?.[0] || data.detail || 'We could not send the photo. Try again.')
      setStage('preview')
    }
  }

  return (
    <section aria-labelledby="selfie-heading" className="space-y-4">
      <h2 id="selfie-heading" className="text-section-title text-ink">
        Take a selfie
      </h2>
      <p className="text-body text-ink-soft">
        A quick live photo of you holding your ID, so an administrator can see the ID is yours. You&apos;ll use your
        camera; there is no upload from your gallery.
      </p>

      {stage === 'start' && (
        <button type="button" className={primary} onClick={() => newChallenge()}>
          Start the selfie step
        </button>
      )}

      {challenge && stage !== 'start' && (
        <div className="rounded-tile bg-sun-light text-sun-ink p-4" aria-live="polite">
          <p className="text-label">Your challenge</p>
          <p className="text-section-title mt-1">{challenge.text}</p>
          <p className="text-caption mt-1">Valid until {timeOf(challenge.expires_at)}. Each challenge works once.</p>
        </div>
      )}

      {stage === 'consent' && (
        <div className="space-y-4">
          <label htmlFor={consentId} className="flex items-start gap-3 text-body text-ink">
            <input
              id={consentId}
              type="checkbox"
              checked={consent}
              onChange={(e) => setConsent(e.target.checked)}
              className="mt-1 w-5 h-5 accent-primary shrink-0"
            />
            <span>{challenge.consent_text}</span>
          </label>
          <button type="button" className={primary} disabled={!consent} onClick={startCamera}>
            Open the camera
          </button>
          {cameraProblem && (
            <div role="alert" className="rounded-input bg-coral-light text-coral-ink p-4 text-body space-y-2">
              <p>{CAMERA_MESSAGES[cameraProblem]}</p>
              <p>
                You can carry on with your phone instead. Open this page there and log in:{' '}
                <span className="font-semibold break-all">{window.location.href}</span>
              </p>
              <p className="text-caption">Phones only allow the camera on the site&apos;s secure (https) address.</p>
            </div>
          )}
        </div>
      )}

      {stage === 'camera' && (
        <div className="space-y-3">
          <div className="relative mx-auto w-full max-w-[420px] aspect-[3/4] rounded-tile overflow-hidden bg-ink">
            <video
              ref={video}
              aria-label="Camera preview"
              playsInline
              muted
              autoPlay
              className="w-full h-full object-cover -scale-x-100"
            />
            {/* The oval face guide. */}
            <div
              aria-hidden="true"
              className="absolute left-1/2 top-[44%] -translate-x-1/2 -translate-y-1/2 w-[58%] h-[62%] rounded-[50%] border-4 border-white/90 shadow-[0_0_0_9999px_rgba(30,27,46,0.45)]"
            />
          </div>
          <p className="text-caption text-muted text-center">Fit your face in the oval and do the challenge.</p>
          <div className="flex justify-center">
            <button type="button" className={primary} onClick={takePhoto}>
              Take photo
            </button>
          </div>
        </div>
      )}

      {(stage === 'preview' || stage === 'sending') && photo && (
        <div className="space-y-3">
          <img
            src={photo.url}
            alt="Your selfie, before sending"
            className="mx-auto w-full max-w-[420px] rounded-tile object-cover"
          />
          <div className="flex flex-wrap justify-center gap-3">
            <button type="button" className={secondary} onClick={retake} disabled={stage === 'sending'}>
              Retake
            </button>
            <button type="button" className={primary} onClick={usePhoto} disabled={stage === 'sending'}>
              {stage === 'sending' ? 'Sending…' : 'Use photo'}
            </button>
          </div>
        </div>
      )}

      {message && (
        <p role="alert" className="text-body text-coral-ink">
          {message}
        </p>
      )}
    </section>
  )
}
