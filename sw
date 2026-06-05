self.addEventListener('push', function(event) {
    const data = event.data ? event.data.json() : { title: 'TFC Хабарнома', body: 'Хабари нав!' };
    
    const options = {
        body: data.body,
        icon: 'https://cdn-icons-png.flaticon.com/512/1046/1046788.png',
        badge: 'https://cdn-icons-png.flaticon.com/512/1046/1046788.png',
        vibrate: [200, 100, 200],
        data: { url: '/' }
    };

    event.waitUntil(
        self.registration.showNotification(data.title, options)
    );
});

self.addEventListener('notificationclick', function(event) {
    event.notification.close();
    event.waitUntil(
        clients.openWindow(event.notification.data.url)
    );
});