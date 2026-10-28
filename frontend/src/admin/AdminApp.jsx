import { Navigate, Route, Routes } from 'react-router-dom'
import AdminLayout from './AdminLayout'
import ApplicationsPage from './pages/ApplicationsPage'
import AuditLogPage from './pages/AuditLogPage'
import GigPreviewPage from './pages/GigPreviewPage'
import GigsPage from './pages/GigsPage'
import OverviewPage from './pages/OverviewPage'
import RecommenderPage from './pages/RecommenderPage'
import UserDetailPage from './pages/UserDetailPage'
import UsersPage from './pages/UsersPage'
import VerificationsPage from './pages/VerificationsPage'

// Everything under /admin. App.jsx loads this file lazily, so other users never download the admin pages.
export default function AdminApp() {
  return (
    <Routes>
      <Route element={<AdminLayout />}>
        <Route index element={<OverviewPage />} />
        <Route path="users" element={<UsersPage />} />
        <Route path="users/:id" element={<UserDetailPage />} />
        <Route path="verifications" element={<VerificationsPage />} />
        <Route path="gigs" element={<GigsPage />} />
        <Route path="gigs/:id" element={<GigPreviewPage />} />
        <Route path="applications" element={<ApplicationsPage />} />
        <Route path="audit-log" element={<AuditLogPage />} />
        <Route path="recommender" element={<RecommenderPage />} />
        <Route path="*" element={<Navigate to="/admin" replace />} />
      </Route>
    </Routes>
  )
}
