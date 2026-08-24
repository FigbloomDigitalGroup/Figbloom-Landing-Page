// ============================================================
// SHARED PAGE BEHAVIOUR
//
// The navbar, footer and prices partials used to be fetched here and injected
// with innerHTML. They are now server-rendered via Django {% include %}, which
// removes two round trips and the layout shift, and means the <script> blocks
// inside those partials actually execute (innerHTML never runs scripts — that
// is why the footer's newsletter handler had to be duplicated here, and why the
// navbar's staff "Admin" link never appeared at all).
//
// Consequences of that move, handled below:
//   - Alpine now initialises the partials itself on load; no initTree needed.
//   - Lucide icons still need one createIcons() call, which used to live in the
//     component loader. Without it every data-lucide icon renders as nothing.
//   - The newsletter form is bound by footer.html's own script now, so binding
//     it here too would attach two submit handlers and double-post.
// ============================================================


// ============================================================
// ALPINE ROOT DATA (body x-data="mainFunction()")
// ============================================================

function mainFunction() {
    return {
        contactModal: false,
    };
}


// ============================================================
// "GET A QUOTE" MODAL FORM (footer.html, opened via contactModal)
// Posts to the same /api/contact/ endpoint as the /contact/ page form.
// ============================================================

function quoteForm() {
    return {
        form: {
            fullName: '',
            email: '',
            service: '',
            brief: '',
            budget: '',
            timeline: '',
            agree: false,
            website: '', // honeypot — left blank by real visitors
        },
        sending: false,
        success: false,
        errorMsg: '',

        resetForm() {
            this.form = {
                fullName: '',
                email: '',
                service: '',
                brief: '',
                budget: '',
                timeline: '',
                agree: false,
                website: '',
            };
        },

        validate() {
            if (!this.form.fullName.trim()) return 'Please enter your full name.';
            if (!this.form.email.trim()) return 'Please enter your work email.';
            if (!this.form.service) return 'Please select a service you’re interested in.';
            if (!this.form.budget) return 'Please select a project budget.';
            if (!this.form.timeline) return 'Please select an expected timeline.';
            if (!this.form.agree) return 'Please agree to be contacted before submitting.';
            return null;
        },

        async submitForm() {
            this.success = false;
            this.errorMsg = '';

            const validationError = this.validate();
            if (validationError) {
                this.errorMsg = validationError;
                return;
            }

            this.sending = true;

            try {
                const csrfToken = document.cookie
                    .split('; ')
                    .find((row) => row.startsWith('csrftoken='))
                    ?.split('=')[1] || '';

                const response = await fetch('/api/contact/', {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: {
                        'Content-Type': 'application/json',
                        Accept: 'application/json',
                        'X-CSRFToken': csrfToken,
                    },
                    body: JSON.stringify({
                        full_name: this.form.fullName,
                        email: this.form.email,
                        service: this.form.service,
                        brief: this.form.brief,
                        budget: this.form.budget,
                        timeline: this.form.timeline,
                        website: this.form.website,
                    }),
                });

                if (response.ok) {
                    this.success = true;
                    this.resetForm();
                    setTimeout(() => {
                        this.success = false;
                        this.contactModal = false;
                    }, 2000);
                } else {
                    const data = await response.json().catch(() => null);
                    const firstError =
                        data && typeof data === 'object'
                            ? Object.values(data).flat().find((v) => typeof v === 'string')
                            : null;
                    this.errorMsg = firstError || 'We couldn’t send your message. Please try again.';
                }
            } catch (err) {
                this.errorMsg = 'Network error — please check your connection and try again.';
            } finally {
                this.sending = false;
            }
        },
    };
}


// ============================================================
// LUCIDE ICONS
// Renders every static data-lucide element once the DOM is parsed.
// Icons created later by Alpine (x-for / x-if) are handled by the
// $nextTick(() => lucide.createIcons()) calls on the individual pages.
// ============================================================

document.addEventListener("DOMContentLoaded", function () {
    if (window.lucide) {
        lucide.createIcons();
    }
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
    }, { passive: true });

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

    .floating-admin {
        width: 52px;
        height: 52px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 50%;
        background: #111827;
        color: #fff;
        font-weight: 700;
        text-decoration: none;
        box-shadow: 0 6px 18px rgba(0,0,0,0.12);
        transition: transform 0.2s ease, opacity 0.2s ease;
    }

    .floating-admin span {
        font-size: 12px;
        line-height: 1;
    }

    .floating-admin:hover {
        transform: translateY(-4px) scale(1.02);
    }

    @media (prefers-reduced-motion: reduce) {
        .floating-whatsapp,
        .floating-scroll-top {
            transition-duration: 0.01ms;
        }
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
