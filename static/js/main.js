/**
 * Andrey AI Lab — клиентские скрипты.
 * Минимальный набор: мобильное меню и лёгкий параллакс фона.
 */

document.addEventListener('DOMContentLoaded', () => {
    const menuToggle = document.querySelector('.menu-toggle');
    const mainNav = document.querySelector('.main-nav');

    if (menuToggle && mainNav) {
        menuToggle.addEventListener('click', () => {
            const isOpen = mainNav.classList.toggle('is-open');
            menuToggle.setAttribute('aria-expanded', String(isOpen));
        });

        // Закрываем меню при клике по ссылке
        mainNav.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', () => {
                mainNav.classList.remove('is-open');
                menuToggle.setAttribute('aria-expanded', 'false');
            });
        });
    }

    // Гравитационный фон: растягиваем на всю высоту документа
    const gravityBg = document.querySelector('.gravity-bg');
    const gravityLayers = document.querySelectorAll('.gravity-layer');

    function updateGravityHeight() {
        if (!gravityBg) return;
        const docHeight = Math.max(
            document.body.scrollHeight,
            document.documentElement.scrollHeight,
            document.body.offsetHeight,
            document.documentElement.offsetHeight
        );
        gravityBg.style.height = `${docHeight}px`;
        gravityLayers.forEach(layer => {
            layer.style.height = `${docHeight}px`;
        });
    }

    if (gravityBg) {
        updateGravityHeight();
        window.addEventListener('resize', updateGravityHeight);

        // Обновляем высоту после полной загрузки ресурсов и изображений
        window.addEventListener('load', updateGravityHeight);

        // Также обновляем после небольшой задержки на случай динамического контента
        setTimeout(updateGravityHeight, 500);
    }

    // Лёгкий параллакс гравитационного фона по движению мыши
    if (gravityLayers.length && !window.matchMedia('(pointer: coarse)').matches) {
        let targetX = 0;
        let targetY = 0;
        let currentX = 0;
        let currentY = 0;
        let isActive = true;

        document.addEventListener('mousemove', (event) => {
            const centerX = window.innerWidth / 2;
            const centerY = window.innerHeight / 2;
            targetX = (event.clientX - centerX) / centerX;
            targetY = (event.clientY - centerY) / centerY;
        });

        function animate() {
            if (!isActive) return;

            // Плавная интерполяция
            currentX += (targetX - currentX) * 0.04;
            currentY += (targetY - currentY) * 0.04;

            gravityLayers.forEach(layer => {
                const depth = parseFloat(layer.dataset.parallax) || 0.03;
                const moveX = currentX * depth * -60;
                const moveY = currentY * depth * -60;
                layer.style.transform = `translate3d(${moveX}px, ${moveY}px, 0)`;
            });

            requestAnimationFrame(animate);
        }

        animate();

        // Останавливаем анимацию, если вкладка не активна
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                isActive = false;
            } else {
                isActive = true;
                animate();
            }
        });
    }
});
