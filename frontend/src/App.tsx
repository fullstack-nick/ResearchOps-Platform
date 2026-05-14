import { Navigate, Route, Routes } from 'react-router-dom';

import { Shell } from './components/Shell';
import { DashboardPage } from './pages/DashboardPage';
import { DocumentPage } from './pages/DocumentPage';
import { QueuePage } from './pages/QueuePage';
import { UploadPage } from './pages/UploadPage';

export function App() {
  return (
    <Shell>
      <Routes>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/upload" element={<UploadPage />} />
        <Route path="/queues" element={<QueuePage />} />
        <Route path="/queues/:workflowType" element={<QueuePage />} />
        <Route path="/documents/:documentId" element={<DocumentPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Shell>
  );
}
