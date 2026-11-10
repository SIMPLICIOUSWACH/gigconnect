import { MessageSquare } from 'lucide-react'
import { Link } from 'react-router-dom'

const firstName = (name = '') => name.trim().split(/\s+/)[0] || name

// What the client's first message starts as. It lands in the message box, where they can change it before sending.
export function suggestedFirstMessage(name) {
  return `Hi ${firstName(name)}, thanks for applying. Here are the next steps: `
}

const BUTTON = 'inline-flex items-center justify-center gap-2 rounded-button font-bold leading-none'
const SIZES = { md: 'min-h-[44px] px-4 text-[15px]', sm: 'min-h-[36px] px-3 text-[14px]' }

// The client's way into the chat with someone they hired. Until the first message is sent it brings a suggested one.
export function MessageFreelancerButton({ conversationId, name, started = false, size = 'md' }) {
  if (!conversationId) return null
  return (
    <Link
      to={`/messages/${conversationId}`}
      state={started ? undefined : { draft: suggestedFirstMessage(name) }}
      className={`${BUTTON} ${SIZES[size]} bg-primary text-white hover:bg-primary-hover`}
    >
      <MessageSquare size={size === 'sm' ? 16 : 18} aria-hidden="true" />
      Message {name}
    </Link>
  )
}

// The freelancer's way into the chat with the client who hired them.
export function FreelancerMessagesLink({ conversationId, clientName, size = 'md' }) {
  if (!conversationId) return null
  return (
    <Link
      to={`/messages/${conversationId}`}
      aria-label={clientName ? `Messages with ${clientName}` : 'Messages'}
      className={`${BUTTON} ${SIZES[size]} bg-surface text-ink border-2 border-ink hover:bg-sand`}
    >
      <MessageSquare size={size === 'sm' ? 16 : 18} aria-hidden="true" />
      Messages
    </Link>
  )
}
