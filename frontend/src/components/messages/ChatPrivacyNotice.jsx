// What happens to chat messages: who can read them, what happens when an account is deleted, and how long they last.
export default function ChatPrivacyNotice() {
  return (
    <section aria-labelledby="chat-privacy-heading" className="space-y-3 text-body text-ink-soft">
      <h2 id="chat-privacy-heading" className="text-section-title text-ink">
        Your messages
      </h2>
      <dl className="space-y-3">
        <div>
          <dt className="text-label text-ink">Who can read them</dt>
          <dd>
            Only you and the person you are chatting with. GigConnect administrators can&apos;t browse chats. They can
            read a chat only after one of you reports it, and every time an administrator opens a reported chat, that
            is recorded in our audit log.
          </dd>
        </div>
        <div>
          <dt className="text-label text-ink">If an account is deleted</dt>
          <dd>
            The other person keeps the chat, so they still have what was agreed. The deleted account is shown as
            &quot;Deleted user&quot; and the chat becomes read-only. Before you delete your account, download your
            data: it includes every message you sent.
          </dd>
        </div>
        <div>
          <dt className="text-label text-ink">How long we keep them</dt>
          <dd>
            A chat becomes read-only 30 days after its gig is completed or closed, or straight away if the gig or the
            application is removed or either account is suspended or deleted. We delete the whole conversation 12
            months after it becomes read-only.
          </dd>
        </div>
      </dl>
    </section>
  )
}
