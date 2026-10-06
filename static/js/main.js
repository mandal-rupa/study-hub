document.addEventListener("DOMContentLoaded", function () {

  const searchInput = document.getElementById("searchInput");
  const filters = document.querySelectorAll(".js-filter");
  const cards = document.querySelectorAll(".resource-card");

  function applyFilters() {
    const searchValue = searchInput.value.toLowerCase();

    cards.forEach(card => {
      const text = card.innerText.toLowerCase();
      card.style.display = text.includes(searchValue) ? "block" : "none";
    });

    checkEmptyState();
  }

  function checkEmptyState() {
    const visibleCards = [...cards].filter(
      c => c.style.display !== "none"
    );

    document.getElementById("noResults").style.display =
      visibleCards.length === 0 ? "block" : "none";
  }

  if (searchInput) {
    searchInput.addEventListener("keyup", applyFilters);
  }

});
// SUBJECT TABS LOGIC
const tabs = document.querySelectorAll(".tab");
const cards = document.querySelectorAll(".resource-card");

tabs.forEach(tab => {
  tab.addEventListener("click", () => {

    // active tab highlight
    tabs.forEach(t => t.classList.remove("active"));
    tab.classList.add("active");

    const subject = tab.getAttribute("data-subject");

    cards.forEach(card => {
      const cardSubject = card.getAttribute("data-subject");

      if (subject === "all" || cardSubject.includes(subject)) {
        card.style.display = "block";
      } else {
        card.style.display = "none";
      }
    });
  });
});
