document.querySelectorAll('.message-close').forEach((button) => {
  button.addEventListener('click', () => button.closest('.message').remove());
});

document.querySelectorAll('form[data-confirm]').forEach((form) => {
  form.addEventListener('submit', (event) => {
    if (!window.confirm(form.dataset.confirm)) event.preventDefault();
  });
});
