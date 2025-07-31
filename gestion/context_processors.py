from .models import Notification, Agence

def notifications_processor(request):
    if request.user.is_authenticated and request.user.user_type == 'AG':
        try:
            agence = request.user.agence
            unread_notifications = Notification.objects.filter(agence=agence, is_read=False)
            return {
                'unread_notifications': unread_notifications[:5], # Affiche les 5 plus récentes
                'unread_notifications_count': unread_notifications.count(),
            }
        except Agence.DoesNotExist:
            pass
    return {}