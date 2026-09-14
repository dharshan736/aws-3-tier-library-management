const roleButtons = document.querySelectorAll('.role-option');
const form = document.querySelector('#login-form');
let selectedRole = 'borrower';
roleButtons.forEach((button) => button.addEventListener('click', () => {
  roleButtons.forEach((item) => item.classList.remove('is-selected'));
  button.classList.add('is-selected');
  selectedRole = button.dataset.role;
  const defaults = { borrower: ['borrower@library.local', 'borrower123'], librarian: ['librarian@library.local', 'librarian123'], admin: ['admin@library.local', 'admin123'] };
  form.email.value = defaults[selectedRole][0]; form.password.value = defaults[selectedRole][1];
}));
form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const error = document.querySelector('#login-error'); error.textContent = '';
  const response = await fetch('/api/login', { method: 'POST', credentials: 'include', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ email: form.email.value, password: form.password.value, role: selectedRole.toUpperCase() }) });
  const contentType = response.headers.get('content-type') || '';
  const data = contentType.includes('application/json') ? await response.json() : { error: `API server returned ${response.status}. Check the Nginx /api/ proxy.` };
  if (!response.ok) { error.textContent = data.error; return; }
  window.location.href = data.redirect;
});