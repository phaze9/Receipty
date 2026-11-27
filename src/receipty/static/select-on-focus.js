document.querySelectorAll('.toolbar input[type="text"], .toolbar input:not([type]), .toolbar input[type="search"]').forEach((input) => {
  input.addEventListener('focus', () => {
    // Defer past the browser's own caret/selection placement on click.
    setTimeout(() => input.select(), 0);
  });
  // Click path: re-assert selection after the mouseup settles.
  input.addEventListener('click', () => input.select());
});
