// ===========================================================================
// Selection and the detail card's photo carousel
// ===========================================================================
var selectedListing = null; // listing pinned in the detail card
var boxSelection = []; // listings picked with shift+drag
var cardPhotos = [];
var cardPhotoIndex = 0;

function stepPhoto(direction) {
    if (cardPhotos.length === 0) return;
    cardPhotoIndex =
        (cardPhotoIndex + direction + cardPhotos.length) % cardPhotos.length;
    byId("card-photo").src = cardPhotos[cardPhotoIndex];
    animateIn(byId("card-photo"), { autoAlpha: 0.4 }, 0.25);
    byId("card-photo-counter").textContent =
        cardPhotoIndex + 1 + " / " + cardPhotos.length;
}
function selectListing(d, e) {
    selectedListing = d;
    showDetailCard(e, d);
    detailCard.style.display = "block";
    detailCard.style.pointerEvents = "auto";
    refreshMap(); // re-render to highlight the marker
    var card = document.querySelector(
        '.listing-card[data-url="' + CSS.escape(d.url) + '"]',
    );
    if (card) {
        card.scrollIntoView({ block: "nearest" });
        card.classList.add("active");
    }
}
function deselectListing() {
    selectedListing = null;
    detailCard.style.display = "none";
    detailCard.style.pointerEvents = "none";
    refreshMap();
}
