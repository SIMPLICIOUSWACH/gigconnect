import { Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider } from './context/AuthContext'
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
import Dashboard from './pages/Dashboard'
import GigForm from './pages/gigs/GigForm'
import GigDetail from './pages/gigs/GigDetail'
import MyGigs from './pages/gigs/MyGigs'
import AccountSettings from './pages/settings/AccountSettings'
import SecuritySettings from './pages/settings/SecuritySettings'
import NotificationSettings from './pages/settings/NotificationSettings'
import PrivacySettings from './pages/settings/PrivacySettings'
import CompanyProfileSettings from './pages/settings/CompanyProfileSettings'
import FreelancerProfileSettings from './pages/settings/FreelancerProfileSettings'
import VerificationSettings from './pages/settings/VerificationSettings'

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

        <Route element={<ProtectedRoute />}>
          <Route path="/verify-phone" element={<VerifyPhone />} />
          <Route path="/profile-setup" element={<ProfileSetup />} />

          <Route element={<Layout />}>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/profile/:id" element={<PublicProfile />} />
            <Route path="/gigs/:id" element={<GigDetail />} />

            <Route element={<RoleRoute role="client" />}>
              <Route path="/gigs/new" element={<GigForm />} />
              <Route path="/gigs/mine" element={<MyGigs />} />
              <Route path="/gigs/:id/edit" element={<GigForm />} />
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
                <Route path="freelancer-profile" element={<FreelancerProfileSettings />} />
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
