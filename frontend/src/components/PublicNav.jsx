import { Link } from 'react-router-dom'
import Button from './Button'

export default function PublicNav() {
  return (
    <nav className="bg-surface border-b border-border">
      <div className="h-16 px-8 flex items-center justify-between max-w-[1100px] mx-auto">
        <Link to="/" className="flex items-center gap-2 text-[17px] font-semibold text-primary">
          <span className="w-2.5 h-2.5 rounded-full bg-primary inline-block" />
          GigConnect
        </Link>
        <div className="flex items-center gap-6">
          <Link to="/about" className="text-nav text-muted hover:text-ink transition-colors duration-150">
            About
          </Link>
          <Link to="/login" className="text-nav text-muted hover:text-ink transition-colors duration-150">
            Log in
          </Link>
          <Link to="/register">
            <Button className="py-2 px-4">Sign up</Button>
          </Link>
        </div>
      </div>
    </nav>
  )
}
