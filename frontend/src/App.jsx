import { Suspense, lazy } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
import AdminRoute from './components/AdminRoute'
import Layout from './components/Layout'
import ProtectedRoute from './components/ProtectedRoute'
import PublicLayout from './components/PublicLayout'
import RoleRoute from './components/RoleRoute'
import SettingsLayout from './layouts/SettingsLayout'

import About from './pages/About'
import Home from './pages/Home'
import Login from './pages/Login'
import Register from './pages/Register'
import VerifyEmail from './pages/VerifyEmail'
import VerifyPhone from './pages/VerifyPhone'
import ProfileSetup from './pages/ProfileSetup'
import PublicProfile from './pages/PublicProfile'
import ProfileEditPage from './pages/profile/ProfileEditPage'
import Dashboard from './pages/Dashboard'
import GigForm from './pages/gigs/GigForm'
import GigDetail from './pages/gigs/GigDetail'
import BrowseGigs from './pages/gigs/BrowseGigs'
import MyGigs from './pages/gigs/MyGigs'
import ApplicationDetail from './pages/applications/ApplicationDetail'
import GigApplicants from './pages/applications/GigApplicants'
import MyApplications from './pages/applications/MyApplications'
import AccountSettings from './pages/settings/AccountSettings'
import SecuritySettings from './pages/settings/SecuritySettings'
import NotificationSettings from './pages/settings/NotificationSettings'
import PrivacySettings from './pages/settings/PrivacySettings'
import CompanyProfileSettings from './pages/settings/CompanyProfileSettings'
import VerificationSettings from './pages/settings/VerificationSettings'

// The admin area is its own bundle, downloaded only when an admin opens it.
const AdminApp = lazy(() => import('./admin/AdminApp'))

function AdminLoading() {
  return <p className="min-h-screen bg-bg p-8 text-body text-muted">Loading the admin area…</p>
}

function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route element={<PublicLayout />}>
          <Route path="/" element={<Home />} />
          <Route path="/about" element={<About />} />
        </Route>
        <Route path="/register" element={<Register />} />
        <Route path="/login" element={<Login />} />
        <Route path="/verify-email/:token" element={<VerifyEmail />} />

        <Route
          path="/admin/*"
          element={
            <AdminRoute>
              <Suspense fallback={<AdminLoading />}>
                <AdminApp />
              </Suspense>
            </AdminRoute>
          }
        />

        <Route element={<ProtectedRoute />}>
          <Route path="/verify-phone" element={<VerifyPhone />} />
          <Route path="/profile-setup" element={<ProfileSetup />} />

          <Route element={<Layout />}>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/profile/:id" element={<PublicProfile />} />
            <Route path="/gigs" element={<BrowseGigs />} />
            <Route path="/gigs/:id" element={<GigDetail />} />
            <Route path="/applications/:id" element={<ApplicationDetail />} />

            <Route element={<RoleRoute role="freelancer" />}>
              <Route path="/applications" element={<MyApplications />} />
              <Route path="/profile/edit" element={<ProfileEditPage />} />
            </Route>

            <Route element={<RoleRoute role="client" />}>
              <Route path="/gigs/new" element={<GigForm />} />
              <Route path="/gigs/mine" element={<MyGigs />} />
              <Route path="/gigs/:id/edit" element={<GigForm />} />
              <Route path="/gigs/:id/applicants" element={<GigApplicants />} />
            </Route>

            <Route path="/settings" element={<SettingsLayout />}>
              <Route index element={<Navigate to="account" replace />} />
              <Route path="account" element={<AccountSettings />} />
              <Route path="security" element={<SecuritySettings />} />
              <Route path="notifications" element={<NotificationSettings />} />
              <Route path="privacy" element={<PrivacySettings />} />

              <Route element={<RoleRoute role="client" />}>
                <Route path="company-profile" element={<CompanyProfileSettings />} />
              </Route>
              <Route element={<RoleRoute role="freelancer" />}>
                <Route path="freelancer-profile" element={<Navigate to="/profile/edit" replace />} />
                <Route path="verification" element={<VerificationSettings />} />
              </Route>
            </Route>
          </Route>
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  )
}

export default App
