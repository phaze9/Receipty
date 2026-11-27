document.querySelectorAll('.date-field').forEach((wrapper) => {
  const form = wrapper.closest('form') || wrapper;
  const picker = wrapper.querySelector('.date-picker');
  const todo = form.querySelector('.todo-toggle input[type="checkbox"]');
  const hidden = form.querySelector('input[type="hidden"][name="date"]');
  if (!picker || !todo || !hidden) return;
  const sync = () => {
    const isTodo = todo.checked;
    picker.disabled = isTodo;
    picker.classList.toggle('dimmed', isTodo);
    hidden.value = isTodo ? 'todo' : picker.value;
  };
  todo.addEventListener('change', sync);
  picker.addEventListener('change', sync);
  sync();
});
