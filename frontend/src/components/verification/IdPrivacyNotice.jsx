import { useEffect, useState } from 'react'
import { fetchPrivacyInfo } from '../../api/profile'

// What GigConnect keeps for ID verification, why, who sees it, how long, and how to ask for it to be deleted.
export default function IdPrivacyNotice() {
  const [info, setInfo] = useState(null)

  useEffect(() => {
    fetchPrivacyInfo()
      .then(setInfo)
      .catch(() => setInfo({ contact_email: '', id_image_retention_days: 90 }))
  }, [])

  const days = info?.id_image_retention_days ?? 90
  const contact = info?.contact_email

  return (
    <section aria-labelledby="id-privacy-heading" className="space-y-3 text-body text-ink-soft">
      <h2 id="id-privacy-heading" className="text-section-title text-ink">
        ID verification and your selfie
      </h2>
      <dl className="space-y-3">
        <div>
          <dt className="text-label text-ink">What we collect</dt>
          <dd>
            Your ID number, a photo or PDF of your ID, and a live selfie of you holding it, taken with your camera. We
            also keep the challenge you were shown, when you agreed to the selfie, and an automatic similarity score
            between the two faces. The score is only a hint for the reviewer, never a decision.
          </dd>
        </div>
        <div>
          <dt className="text-label text-ink">Why</dt>
          <dd>To confirm you are who you say you are, and to stop one ID being used for more than one account.</dd>
        </div>
        <div>
          <dt className="text-label text-ink">Who sees it</dt>
          <dd>
            Only GigConnect administrators. Clients, other freelancers and the public never see your ID or selfie, and
            no web link leads to them.
          </dd>
        </div>
        <div>
          <dt className="text-label text-ink">How long we keep it</dt>
          <dd>
            The ID image, the selfie and your ID number are deleted {days} days after an administrator approves or
            rejects your check, and straight away if you delete your account. After that we keep only the decision,
            its dates and the similarity score, plus a scrambled code made from your ID number (a keyed hash) and its
            last 3 digits. The code can&apos;t be turned back into the number; it only lets us notice if the same ID
            is used again.
          </dd>
        </div>
        <div>
          <dt className="text-label text-ink">Asking for deletion</dt>
          <dd>
            Deleting your account below removes your ID images and number at once.{' '}
            {contact ? (
              <>
                For anything else, or to ask for deletion without closing your account, email{' '}
                <a href={`mailto:${contact}`} className="text-primary font-semibold hover:underline">
                  {contact}
                </a>
                .
              </>
            ) : (
              'For anything else, contact a GigConnect administrator.'
            )}
          </dd>
        </div>
      </dl>
    </section>
  )
}
