import { Link } from 'react-router-dom'

export default function PublicFooter() {
  return (
    <footer className="border-t border-border">
      <div className="max-w-[1100px] mx-auto px-8 py-8 flex items-center justify-between">
        <div className="flex items-center gap-2 text-[15px] font-semibold text-primary">
          <span className="w-2 h-2 rounded-full bg-primary inline-block" />
          GigConnect
        </div>
        <div className="flex items-center gap-6 text-caption text-muted">
          <Link to="/about" className="hover:text-ink transition-colors duration-150">
            About
          </Link>
          <span>A capstone project — BSc Informatics & Computer Science, Strathmore University</span>
        </div>
      </div>
    </footer>
  )
}
