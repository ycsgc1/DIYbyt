import React from 'react'
import ReactDOM from 'react-dom/client'
import DisplayControl from './components/DisplayControl'

// You can add global styles here if needed
// import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <div className="app-container">
      <header>
        <h1>DIYbyt Control Panel</h1>
      </header>
      <main>
        <DisplayControl />
      </main>
    </div>
  </React.StrictMode>
)