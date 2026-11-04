// Keep the clicked heading still while its summary opens or closes.
document.addEventListener("click", (event) => {
  const heading = event.target.closest(".summary-card > summary");
  if (!heading) return;

  const previousTop = heading.getBoundingClientRect().top;
  requestAnimationFrame(() => {
    const movement = heading.getBoundingClientRect().top - previousTop;
    if (Math.abs(movement) > 1) window.scrollBy(0, movement);
  });
});
