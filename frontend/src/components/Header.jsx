import React from 'react'
import { Link } from 'react-router-dom'
import './Header.css'

function Header() {
    return (
        <header className="header">
            <div className="header-container">
                <div className="header-brand">
                    <h1>VA/NVA Analysis</h1>
                </div>
                <nav className="header-nav">
                    <Link to="/" className="nav-link">Dashboard</Link>
                    <Link to="/upload" className="nav-link">Upload Video</Link>
                    <Link to="/clipper" className="nav-link">Video Clipper</Link>
                    <Link to="/predict-action" className="nav-link">Predict Action</Link>
                    {/* Worker review and analytics are typically accessed via links from the Dashboard */}
                </nav>
            </div>
        </header>
    )
}

export default Header
