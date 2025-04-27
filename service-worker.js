console.log('SW carregado e ativo');

self.addEventListener('push', event => {
  console.log('Push event recebido:', event);

  let data = {};
  if (event.data) {
    try {
      data = event.data.json();               // tenta JSON
    } catch (err) {
      console.warn('Payload não era JSON, caindo para text():', err);
      const text = event.data.text();         // pega texto
      data = { title: 'Moedinhas', body: text };
    }
  }

  const title = data.title || 'Moedinhas';
  const options = {
    body:   data.body  || '',
    icon:   '/static/moedinha.png',
    badge:  '/static/badge.png'  // opcional
  };

  console.log('Exibindo notificação:', title, options);
  event.waitUntil(self.registration.showNotification(title, options));
});
