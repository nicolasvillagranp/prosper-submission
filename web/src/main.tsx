import { createRoot } from 'react-dom/client'

import App from './App'
import './styles.css'

// No StrictMode: its double effects in development would join the interview room twice.
createRoot(document.getElementById('app')!).render(<App />)
