import { Link } from "react-router-dom";

export default function NavBar() {
  return (
    <nav className="border-b border-[#2a2d3a] bg-[#1a1d27] px-6 py-3 flex items-center justify-between">
      <Link to="/" className="flex items-center gap-2 text-white font-semibold text-sm tracking-wide hover:opacity-80 transition-opacity">
        <span className="text-lg">🎬</span>
        Brand Integration Auditor
      </Link>
      <div className="flex items-center gap-4 text-sm text-slate-400">
        <Link to="/" className="hover:text-white transition-colors">New Audit</Link>
        <Link to="/jobs" className="hover:text-white transition-colors">Recent Jobs</Link>
      </div>
    </nav>
  );
}
