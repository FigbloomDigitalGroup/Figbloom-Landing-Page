// ============================================================
// SHARED COMPONENT LOADER
// ============================================================

async function loadComponent(elementId, componentPath) {
    const element = document.getElementById(elementId);

    if (!element) return;

    try {
        const response = await fetch(componentPath);

        if (!response.ok) {
            throw new Error(`Failed to load ${componentPath}`);
        }

        element.innerHTML = await response.text();

        // Reinitialize Alpine.js after inserting the component
        if (window.Alpine) {
            window.Alpine.initTree(element);
        }

        // Reinitialize Lucide icons
        if (window.lucide) {
            lucide.createIcons();
        }

    } catch (error) {
        console.error("Component loading error:", error);
    }
}


// ============================================================
// NEWSLETTER FORM
// Must run AFTER footer.html is injected, and must be attached
// here (not inside footer.html) because <script> tags inserted
// via innerHTML never execute in the browser.
// ============================================================

function initNewsletterForm() {
    const form = document.getElementById('newsletter-form');

    if (!form || form.dataset.bound) return;
    form.dataset.bound = 'true';

    const success = document.getElementById('newsletter-success');
    const error = document.getElementById('newsletter-error');

    form.addEventListener('submit', async function (event) {
        event.preventDefault();

        const name = document.getElementById('newsletter-name').value.trim();
        const email = document.getElementById('newsletter-email').value.trim();

        success.classList.add('hidden');
        error.classList.add('hidden');
        error.textContent = '';

        if (!name || !email) {
            error.textContent = 'Please enter your name and email address.';
            error.classList.remove('hidden');
            return;
        }

        const formData = new FormData();
        formData.append('name', name);
        formData.append('email', email);

        try {
            const csrfToken = document.cookie
                .split('; ')
                .find((row) => row.startsWith('csrftoken='))
                ?.split('=')[1] || '';

            const response = await fetch('/api/newsletter/subscribe/', {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    'X-CSRFToken': csrfToken
                },
                body: formData
            });

            if (!response.ok) {
                throw new Error('Unable to submit subscription');
            }

            form.reset();
            success.classList.remove('hidden');
        } catch (fetchError) {
            console.error('Newsletter subscription error:', fetchError);
            error.textContent = 'Unable to subscribe right now. Please try again later.';
            error.classList.remove('hidden');
        }
    });
}


// ============================================================
// LOAD NAVBAR + FOOTER (every page that has these containers)
// ============================================================

document.addEventListener("DOMContentLoaded", async () => {
    await loadComponent("navbar", "/components/navbar.html");
    await loadComponent("footer", "/components/footer.html");
    initNewsletterForm();
});


// ============================================================
// LOAD HEADER
// ============================================================

document.addEventListener("DOMContentLoaded", async () => {
    try {
        const response = await fetch("/components/header.html");

        if (!response.ok) {
            throw new Error("Could not load components/header.html");
        }

        const headerHTML = await response.text();

        document.head.insertAdjacentHTML("beforeend", headerHTML);

    } catch (error) {
        console.error("Header component error:", error);
    }
});


// ============================================================
// LOAD PRICES COMPONENT (only present on pages with #prices)
// ============================================================

function mainFunction() {
    return {
        contactModal: false,
    };
}

document.addEventListener("DOMContentLoaded", () => {
    loadComponent("prices", "/components/prices.html");
});


// ============================================================
// FLOATING WHATSAPP + SCROLL TO TOP BUTTONS
// ============================================================

document.addEventListener("DOMContentLoaded", function () {
    const floatingButtons = document.createElement("div");

    floatingButtons.className = "floating-action-buttons";

    floatingButtons.innerHTML = `
        <!-- WhatsApp Button -->
        <a
            href="https://wa.me/254796286676"
            target="_blank"
            rel="noopener noreferrer"
            class="floating-whatsapp"
            aria-label="Chat with us on WhatsApp"
        >
            <img
                src="/assets/images/whatsapp-icon.svg"
                alt="WhatsApp"
            />
        </a>

        <!-- Scroll To Top Button -->
        <button
            type="button"
            class="floating-scroll-top"
            aria-label="Scroll to top"
        >
            <img
                src="/assets/images/arrow-up.svg"
                alt="Scroll to top"
            />
        </button>
    `;

    document.body.appendChild(floatingButtons);

    const scrollTopButton = document.querySelector(".floating-scroll-top");

    window.addEventListener("scroll", function () {
        if (window.scrollY > 400) {
            scrollTopButton.classList.add("is-visible");
        } else {
            scrollTopButton.classList.remove("is-visible");
        }
    });

    scrollTopButton.addEventListener("click", function () {
        window.scrollTo({
            top: 0,
            behavior: "smooth",
        });
    });
});


const floatingButtonStyles = document.createElement("style");

floatingButtonStyles.innerHTML = `
    .floating-action-buttons {
        position: fixed;
        right: 24px;
        bottom: 24px;
        z-index: 9999;
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 12px;
    }

    .floating-whatsapp,
    .floating-scroll-top {
        width: 52px;
        height: 52px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 50%;
        transition: all 0.3s ease;
    }

    .floating-whatsapp img {
        width: 50px;
        height: 60px;
        object-fit: contain;
    }

    .floating-scroll-top {
        border: none;
        cursor: pointer;
        background: #FF9400;
        opacity: 0;
        visibility: hidden;
        transform: translateY(15px);
    }

    .floating-scroll-top img {
        width: 24px;
        height: 24px;
        object-fit: contain;
    }

    .floating-scroll-top.is-visible {
        opacity: 1;
        visibility: visible;
        transform: translateY(0);
    }

    .floating-whatsapp:hover,
    .floating-scroll-top:hover {
        transform: translateY(-4px);
    }

    @media (max-width: 640px) {
        .floating-action-buttons {
            right: 16px;
            bottom: 16px;
            gap: 10px;
        }

        .floating-whatsapp,
        .floating-scroll-top {
            width: 46px;
            height: 46px;
        }

        .floating-whatsapp img {
            width: 40px;
            height: 40px;
        }

        .floating-scroll-top img {
            width: 21px;
            height: 21px;
        }
    }
`;

document.head.appendChild(floatingButtonStyles);