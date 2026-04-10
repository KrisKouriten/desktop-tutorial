/* ============================================================
   ClearLedger Consulting - Main JavaScript
   ============================================================ */

document.addEventListener('DOMContentLoaded', () => {
  initNavigation();
  initScrollReveal();
  initStatCounters();
  initContactForm();
  initActiveNavHighlight();
});

/* === NAVIGATION === */
function initNavigation() {
  const toggle = document.getElementById('nav-toggle');
  const menu = document.getElementById('nav-menu');
  const header = document.getElementById('header');
  const navLinks = menu.querySelectorAll('.nav__link');

  // Mobile menu toggle
  toggle.addEventListener('click', () => {
    const isOpen = menu.classList.toggle('open');
    toggle.setAttribute('aria-expanded', isOpen);
  });

  // Close menu when a link is clicked
  navLinks.forEach(link => {
    link.addEventListener('click', () => {
      menu.classList.remove('open');
      toggle.setAttribute('aria-expanded', 'false');
    });
  });

  // Close menu when clicking outside
  document.addEventListener('click', (e) => {
    if (!menu.contains(e.target) && !toggle.contains(e.target)) {
      menu.classList.remove('open');
      toggle.setAttribute('aria-expanded', 'false');
    }
  });

  // Header scroll effect
  const onScroll = () => {
    header.classList.toggle('header--scrolled', window.scrollY > 20);
  };
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();
}

/* === SCROLL REVEAL === */
function initScrollReveal() {
  const revealElements = document.querySelectorAll(
    '.service-card, .pricing-card, .testimonial-card, .portal-feature, .about__content, .about__image-card, .contact__info, .contact__form'
  );

  revealElements.forEach(el => el.classList.add('reveal'));

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.1, rootMargin: '0px 0px -40px 0px' }
  );

  revealElements.forEach(el => observer.observe(el));
}

/* === STAT COUNTER ANIMATION === */
function initStatCounters() {
  const statNumbers = document.querySelectorAll('.stat__number[data-target]');

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          animateCounter(entry.target);
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.5 }
  );

  statNumbers.forEach(el => observer.observe(el));
}

function animateCounter(element) {
  const target = parseInt(element.getAttribute('data-target'), 10);
  const duration = 2000;
  const start = performance.now();

  function update(now) {
    const elapsed = now - start;
    const progress = Math.min(elapsed / duration, 1);
    // Ease-out cubic
    const eased = 1 - Math.pow(1 - progress, 3);
    element.textContent = Math.round(target * eased);

    if (progress < 1) {
      requestAnimationFrame(update);
    }
  }

  requestAnimationFrame(update);
}

/* === ACTIVE NAV HIGHLIGHT === */
function initActiveNavHighlight() {
  const sections = document.querySelectorAll('section[id]');
  const navLinks = document.querySelectorAll('.nav__link');

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const id = entry.target.getAttribute('id');
          navLinks.forEach(link => {
            link.classList.toggle('active', link.getAttribute('href') === `#${id}`);
          });
        }
      });
    },
    { threshold: 0.3, rootMargin: '-80px 0px -50% 0px' }
  );

  sections.forEach(section => observer.observe(section));
}

/* === CONTACT FORM === */
function initContactForm() {
  const form = document.getElementById('contact-form');
  const successMsg = document.getElementById('form-success');

  form.addEventListener('submit', (e) => {
    e.preventDefault();

    // Clear previous errors
    form.querySelectorAll('.form-group').forEach(g => g.classList.remove('form-group--error'));

    let isValid = true;

    // Validate name
    const name = form.querySelector('#name');
    if (!name.value.trim()) {
      name.closest('.form-group').classList.add('form-group--error');
      isValid = false;
    }

    // Validate email
    const email = form.querySelector('#email');
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(email.value.trim())) {
      email.closest('.form-group').classList.add('form-group--error');
      isValid = false;
    }

    // Validate service selection
    const service = form.querySelector('#service');
    if (!service.value) {
      service.closest('.form-group').classList.add('form-group--error');
      isValid = false;
    }

    if (!isValid) return;

    // Simulate form submission
    const submitBtn = form.querySelector('button[type="submit"]');
    submitBtn.classList.add('btn--loading');
    submitBtn.disabled = true;

    setTimeout(() => {
      submitBtn.classList.remove('btn--loading');
      submitBtn.disabled = false;
      form.reset();
      successMsg.classList.add('visible');

      // Hide success message after 8 seconds
      setTimeout(() => {
        successMsg.classList.remove('visible');
      }, 8000);
    }, 1500);
  });

  // Remove error state on input
  form.querySelectorAll('.form-input').forEach(input => {
    input.addEventListener('input', () => {
      input.closest('.form-group').classList.remove('form-group--error');
    });
  });
}
