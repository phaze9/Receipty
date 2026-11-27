document.querySelectorAll('.date-field').forEach((wrapper) => {
  const picker = wrapper.querySelector('.date-picker');
  const todo = wrapper.querySelector('.todo-toggle input[type="checkbox"]');
  const hidden = wrapper.querySelector('input[type="hidden"][name="date"]');
  if (!picker || !todo || !hidden) return;
  const sync = () => {
    const isTodo = todo.checked;
    picker.classList.toggle('dimmed', isTodo);
    hidden.value = isTodo ? 'todo' : picker.value;
  };
  todo.addEventListener('change', sync);
  picker.addEventListener('change', sync);
  sync();
});
