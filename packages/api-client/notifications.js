import { request } from './client.js';

export async function getNotifications() {
  return request('/api/notifications', {
    method: 'GET',
  });
}

export async function markNotificationAsRead(notificationId) {
  return request(`/api/notifications/${notificationId}/read`, {
    method: 'PATCH',
  });
}
