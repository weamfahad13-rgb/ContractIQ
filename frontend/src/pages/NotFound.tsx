import { Link } from 'react-router-dom'

export default function NotFound() {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-4 py-16 text-center">
      <img src="/mascots/mascot-chat.webp" alt="" className="h-56 object-contain" />
      <h1 className="text-3xl font-extrabold">Page not found</h1>
      <p className="text-muted">There's nothing at this address.</p>
      <Link to="/chat" className="rounded-xl bg-accent px-6 py-3 font-bold text-ink-950 hover:bg-accent-strong">
        Go to the chat
      </Link>
    </div>
  )
}
