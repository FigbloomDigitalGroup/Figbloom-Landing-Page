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

document.addEventListener("DOMContentLoaded", () => {
    loadComponent("navbar", "/components/navbar.html");
});




//footer 

async function loadComponent(elementId, componentPath) {
    const element = document.getElementById(elementId);

    if (!element) {
        console.error(`Element #${elementId} not found`);
        return;
    }

    try {
        const response = await fetch(componentPath);

        if (!response.ok) {
            throw new Error(`Failed to load ${componentPath}`);
        }

        element.innerHTML = await response.text();

        // Reinitialize Alpine.js for the newly loaded component
        if (window.Alpine) {
            Alpine.initTree(element);
        }

        // Reinitialize Lucide icons
        if (window.lucide) {
            lucide.createIcons();
        }

    } catch (error) {
        console.error("Component loading error:", error);
    }
}


document.addEventListener("DOMContentLoaded", () => {
    loadComponent("navbar", "/components/navbar.html");
    loadComponent("footer", "/components/footer.html");
});



//header
// Load header.html into the <head>
document.addEventListener("DOMContentLoaded", async () => {
    try {
        const response = await fetch("components/header.html");

        if (!response.ok) {
            throw new Error("Could not load components/header.html");
        }

        const headerHTML = await response.text();

        document.head.insertAdjacentHTML("beforeend", headerHTML);

    } catch (error) {
        console.error("Header component error:", error);
    }
});



//prices 
// Main Alpine data
function mainFunction() {
    return {
        contactModal: false,
    };
}


// Load HTML components
async function loadComponent(elementId, componentPath) {
    const element = document.getElementById(elementId);

    if (!element) return;

    try {
        const response = await fetch(componentPath);

        if (!response.ok) {
            throw new Error(`Failed to load ${componentPath}`);
        }

        element.innerHTML = await response.text();

        // Initialize Alpine on the newly loaded component
        if (window.Alpine) {
            Alpine.initTree(element);
        }

        // Re-render Lucide icons
        if (window.lucide) {
            lucide.createIcons();
        }

    } catch (error) {
        console.error("Component loading error:", error);
    }
}


// Load components
document.addEventListener("DOMContentLoaded", () => {

    loadComponent(
        "prices",
        "/components/prices.html"
    );

});









/* =========================================================
   FLOATING WHATSAPP + SCROLL TO TOP BUTTONS
   ========================================================= */

document.addEventListener("DOMContentLoaded", function () {
    /*
    ---------------------------------------------------------
    1. FLOATING ACTION BUTTON CONTAINER
    ---------------------------------------------------------
    */

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


    /*
    ---------------------------------------------------------
    2. SCROLL TO TOP FUNCTIONALITY
    ---------------------------------------------------------
    */

    const scrollTopButton = document.querySelector(
        ".floating-scroll-top"
    );

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


/* =========================================================
   FLOATING BUTTON STYLES
   ========================================================= */

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

    .floating-whatsapp {
      
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

