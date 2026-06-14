self.addEventListener('push', function (event) {
    const data = event.data ? event.data.json() : { title: 'TFC Хабарнома', body: 'Хабари нав!' };

    const options = {
        body: data.body,
        icon: '/static/images/TFC.jpg',
        badge: '/static/images/TFC.jpg',
        vibrate: [200, 100, 200],
        data: { url: '/' }
    };

    event.waitUntil(
        self.registration.showNotification(data.title, options)
    );
});

self.addEventListener('notificationclick', function (event) {
    event.notification.close();
    event.waitUntil(
        clients.openWindow(event.notification.data.url)
    );
});