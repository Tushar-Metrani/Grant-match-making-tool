
const API_URL = 'https://grant-match-making-tool-production.up.railway.app';

async function waitForServer() {
  const loadingMsg = document.getElementById('loadingMsg');
  const loadingScreen = document.getElementById('loadingScreen');
  
  let attempts = 0;
  const maxAttempts = 5;

  while (attempts < maxAttempts) {
    try {
      loadingMsg.textContent = attempts === 0
        ? 'Connecting to server…'
        : 'Server is waking up, please wait…';

      const res = await fetch(`${API_URL}/health`, { method: 'GET' });
      
      if (res.ok) {
        loadingMsg.textContent = 'Ready!';
        console.log("ready");
        await new Promise(r => setTimeout(r, 600));
        loadingScreen.classList.add('fade-out');
        setTimeout(() => loadingScreen.remove(), 500);
        return;
      }
    } catch (e) {
      // server not ready yet
    }

    attempts++;
    await new Promise(r => setTimeout(r, 20000));
  }

  // If server never responded
  loadingMsg.textContent = 'Server unavailable. Please try again later.';
}

waitForServer();
