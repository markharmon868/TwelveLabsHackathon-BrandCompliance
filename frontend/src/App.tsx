import { BrowserRouter, Routes, Route } from "react-router-dom";
import UploadPage from "./pages/UploadPage";
import JobPage from "./pages/JobPage";
import JobsListPage from "./pages/JobsListPage";

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen bg-[#0f1117] text-slate-100">
        <Routes>
          <Route path="/" element={<UploadPage />} />
          <Route path="/jobs" element={<JobsListPage />} />
          <Route path="/jobs/:jobId" element={<JobPage />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}
