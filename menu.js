/**
 * Menu Controller - Dark Fantasy Epic Chess Edition
 * Handles navigation and interactions for the main menu
 */

class MenuController {
    constructor() {
        this.currentPage = 'menu';
        this.buttons = document.querySelectorAll('.menu-btn');
        this.container = document.querySelector('.menu-container');
        this.initEventListeners();
        this.addShineEffects();
    }

    initEventListeners() {
        this.buttons.forEach(btn => {
            btn.addEventListener('click', (e) => {
                const target = btn.dataset.page || btn.dataset.action;
                this.handleNavigation(target, btn);
            });
        });
    }

    addShineEffects() {
        this.buttons.forEach(btn => {
            const shine = document.createElement('div');
            shine.className = 'shine';
            btn.appendChild(shine);
        });
    }

    handleNavigation(target, buttonElement) {
        // Add visual feedback
        if (buttonElement) {
            buttonElement.style.transform = 'translateX(10px) scale(0.98)';
            setTimeout(() => {
                if (buttonElement) {
                    buttonElement.style.transform = '';
                }
            }, 150);
        }
        
        switch(target) {
            case 'play':
                this.showDifficultySelection();
                break;
            case 'howtoplay':
                this.showHowToPlay();
                break;
            case 'rankings':
                this.showRankings();
                break;
            case 'about':
                this.showAboutUs();
                break;
            case 'quit':
                this.confirmQuit();
                break;
            default:
                console.log('Unknown navigation target:', target);
        }
    }

    showDifficultySelection() {
        // Transition to difficulty selection screen
        this.fadeOutMenu(() => {
            // For now, show alert - you can replace this with actual navigation
            alert('Difficulty Selection - Coming Soon!\n\nThis would navigate to the game setup screen.');
            // Uncomment when you have a difficulty selection page:
            // window.location.href = '#/difficulty';
            // Or if using a SPA framework:
            // router.navigate('/difficulty');
        });
    }

    showHowToPlay() {
        this.fadeOutMenu(() => {
            // For now, show alert - you can replace this with actual navigation
            alert('How to Play - Coming Soon!\n\nThis would show the game rules and instructions.');
            // Uncomment when you have a how-to-play page:
            // window.location.href = '#/howtoplay';
        });
    }

    showRankings() {
        this.fadeOutMenu(() => {
            // For now, show alert - you can replace this with actual navigation
            alert('Rankings - Coming Soon!\n\nThis would show the leaderboard and player statistics.');
            // Uncomment when you have a rankings page:
            // window.location.href = '#/rankings';
        });
    }

    showAboutUs() {
        this.fadeOutMenu(() => {
            // For now, show alert - you can replace this with actual navigation
            alert('About Us - Coming Soon!\n\nThis would show information about the game and team.');
            // Uncomment when you have an about page:
            // window.location.href = '#/about';
        });
    }

    confirmQuit() {
        if (confirm('Are you sure you want to quit?')) {
            // Close window if in a web context
            if (window.close) {
                window.close();
            } else {
                // Fallback: redirect or show message
                alert('Thank you for playing Chess Edition!');
                // If running in Electron or similar, you might use:
                // window.electronAPI.quit();
            }
        }
    }

    fadeOutMenu(callback) {
        if (!this.container) {
            if (callback) callback();
            return;
        }
        
        this.container.style.transition = 'opacity 0.5s ease-out, transform 0.5s ease-out';
        this.container.classList.add('fade-out');
        
        setTimeout(() => {
            if (callback) callback();
            this.container.classList.remove('fade-out');
            this.container.style.transition = '';
        }, 500);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const menuController = new MenuController();
    
    const bgImage = new Image();
    bgImage.onerror = () => {
        if (menuController.container) {
            menuController.container.style.backgroundImage = "url('./assets/Decorate/dragon-background.jpg')";
        }
    };
    bgImage.src = 'assets/Decorate/dragon-background.jpg';
});

document.addEventListener('contextmenu', (e) => {
    e.preventDefault();
});

