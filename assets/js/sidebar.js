const md5 = require('md5');
import {postRequest} from './ajax-handler';

export const initSidebar = function (viewportChangeHandler) {
    $('.menu-item-expandable > a').click(function () {
        $('.menu-submenu').slideUp(200);
        if ($(this).parent().hasClass('active')) {
            $('.menu-item-expandable').removeClass('active');
            $(this).parent().removeClass('active');
        }
        else {
            $('.menu-item-expandable').removeClass('active');
            $(this).next('.menu-submenu').slideDown(200);
            $(this).parent().addClass('active');
        }
    });

    $('.siderbar-toggler').click(function () {
        $('#content-wrapper').toggleClass('toggled').toggleClass('not-toggled');
        if (typeof viewportChangeHandler === 'function') {
            setTimeout(viewportChangeHandler, 250);
        }

    });

    let currentPage = $('#sidebar-menu').attr('page');
    $('.menu-item').each(function (idx, menuItemEL) {
        if (menuItemEL.getAttribute('page') === currentPage) {
            $(menuItemEL).addClass('active');
        }
    });

    $('.menu-submenu li').each(function (idx, menuItemEL) {
        if (menuItemEL.getAttribute('page') === currentPage) {
            $(menuItemEL).addClass('active');
            $(menuItemEL).parents('.menu-item-expandable').children('a').click();
        }
    });

    let avatarImg = $('#user-pic img');
    if (avatarImg.length) {
        let userEmail = avatarImg.attr('email');
        avatarImg.attr('email', '');
        let hash = md5(userEmail.trim().toLowerCase());
        let gravatar = `//www.gravatar.com/avatar/${hash}?s=56`;
        avatarImg.attr('src', gravatar);
    }
};


export const replaceSidebar = function (viewportChangeHandler) {
    let wrapper = $('#sidebar-wrapper');
    let pageName = wrapper.attr('page');

    return new Promise(function (resolve) {
        postRequest({
            requestSlug: 'koe/get-sidebar',
            data: {
                page: pageName
            },
            onSuccess(html) {
                wrapper.replaceWith(html);
                initSidebar(viewportChangeHandler);
                resolve();
            },
            immediate: true
        });
    });
};
