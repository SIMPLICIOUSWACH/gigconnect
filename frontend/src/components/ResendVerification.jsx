import { useState } from 'react'
import { resendVerification } from '../api/auth'

// A "Resend verification email" button and the answer it gets back. Signed out, pass the email address; signed in,
// leave it out and the server uses the account's own address.
export default function ResendVerification({ email, label = 'Resend verification email' }) {
  const [state, setState] = useState({ busy: false, message: '', failed: false })

  const resend = async () => {
    setState({ busy: true, message: '', failed: false })
    try {
      const data = await resendVerification(email)
      setState({ busy: false, message: data.detail, failed: false })
    } catch (err) {
      const tooMany = err.response?.status === 429
      setState({
        busy: false,
        failed: true,
        message: tooMany
          ? 'You have asked for a lot of emails. Wait a while, then try again.'
          : err.response?.data?.detail || "We couldn't send the email. Try again in a few minutes.",
      })
    }
  }

  return (
    <span className="inline-flex flex-col gap-1">
      <button
        type="button"
        onClick={resend}
        disabled={state.busy}
        className="self-start underline font-semibold disabled:opacity-60"
      >
        {state.busy ? 'Sending…' : label}
      </button>
      <span role="status" className={state.failed ? 'text-red-700' : ''}>
        {state.message}
      </span>
    </span>
  )
}
