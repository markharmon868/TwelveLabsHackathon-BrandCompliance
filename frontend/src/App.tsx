import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Layout from "./components/Layout";
import SetupPage from "./pages/SetupPage";
import UploadPage from "./pages/UploadPage";
import JobPage from "./pages/JobPage";
import JobsListPage from "./pages/JobsListPage";
import GuidelinesPage from "./pages/GuidelinesPage";
import IntegrationsPage from "./pages/IntegrationsPage";
import { getStoredApiKey } from "./api";

function RequireKey({ children }: { children: React.ReactNode }) {
  return getStoredApiKey() ? <>{children}</> : <Navigate to="/setup" replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/setup" element={<SetupPage />} />
        <Route
          path="/*"
          element={
            <RequireKey>
              <Layout>
                <Routes>
                  <Route path="/" element={<UploadPage />} />
                  <Route path="/jobs" element={<JobsListPage />} />
                  <Route path="/jobs/:jobId" element={<JobPage />} />
                  <Route path="/guidelines" element={<GuidelinesPage />} />
                  <Route path="/integrations" element={<IntegrationsPage />} />
                </Routes>
              </Layout>
            </RequireKey>
          }
        />
      </Routes>
    </BrowserRouter>
  );
}
