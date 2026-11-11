import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
from django.db import models
from .models import (
    RealTimeNotification,
    NotificationPreference,
    ChatRoom,
    ChatMessage,
    ChatParticipant,
    TypingIndicator,
)


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time notifications.
    """

    async def connect(self):
        """Handle WebSocket connection."""
        self.user = self.scope["user"]

        # Check if user is authenticated
        if isinstance(self.user, AnonymousUser):
            await self.close()
            return

        # Join user's notification group
        self.notification_group_name = f"notifications_{self.user.id}"
        await self.channel_layer.group_add(
            self.notification_group_name, self.channel_name
        )

        await self.accept()

        # Send unread notifications count
        await self.send_unread_count()

        # Send recent unread notifications
        await self.send_recent_notifications()

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        # Leave notification group
        if hasattr(self, "notification_group_name"):
            await self.channel_layer.group_discard(
                self.notification_group_name, self.channel_name
            )

    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(text_data)
            message_type = data.get("type")

            if message_type == "mark_read":
                await self.handle_mark_read(data)
            elif message_type == "mark_all_read":
                await self.handle_mark_all_read()
            elif message_type == "get_unread_count":
                await self.send_unread_count()

        except json.JSONDecodeError:
            await self.send(
                text_data=json.dumps(
                    {"type": "error", "message": "Invalid JSON format"}
                )
            )
        except Exception as e:
            await self.send(text_data=json.dumps({"type": "error", "message": str(e)}))

    async def handle_mark_read(self, data):
        """Handle marking notifications as read."""
        notification_ids = data.get("notification_ids", [])
        if notification_ids:
            await self.mark_notifications_read(notification_ids)
            # Send updated count
            await self.send_unread_count()

    async def handle_mark_all_read(self):
        """Handle marking all notifications as read."""
        await self.mark_all_notifications_read()
        # Send updated count
        await self.send_unread_count()

    # Event handlers for group messages
    async def send_notification(self, event):
        """Send notification to WebSocket."""
        await self.send(
            text_data=json.dumps(
                {"type": "notification", "notification": event["notification"]}
            )
        )

        # Update unread count
        await self.send_unread_count()

    # Database operations
    @database_sync_to_async
    def send_unread_count(self):
        """Send current unread notifications count."""
        count = RealTimeNotification.objects.filter(
            recipient=self.user, is_read=False
        ).count()
        await self.send(text_data=json.dumps({"type": "unread_count", "count": count}))

    @database_sync_to_async
    def send_recent_notifications(self):
        """Send recent unread notifications."""
        notifications = (
            RealTimeNotification.objects.filter(recipient=self.user, is_read=False)
            .exclude(
                # Exclude expired notifications
                models.Q(expires_at__isnull=False)
                & models.Q(expires_at__lt=models.functions.Now())
            )
            .select_related()
            .order_by("-created_at")[:10]
        )  # Last 10 notifications

        for notification in notifications:
            formatted_notification = await self.format_notification(notification)
            await self.send(
                text_data=json.dumps(
                    {"type": "notification", "notification": formatted_notification}
                )
            )

    @database_sync_to_async
    def mark_notifications_read(self, notification_ids):
        """Mark specific notifications as read."""
        RealTimeNotification.objects.filter(
            id__in=notification_ids, recipient=self.user
        ).update(is_read=True)

    @database_sync_to_async
    def mark_all_notifications_read(self):
        """Mark all notifications as read for user."""
        RealTimeNotification.objects.filter(recipient=self.user).update(is_read=True)

    @database_sync_to_async
    def format_notification(self, notification):
        """Format notification for WebSocket transmission."""
        return {
            "id": notification.id,
            "type": notification.notification_type,
            "title": notification.title,
            "message": notification.message,
            "priority": notification.priority,
            "created_at": notification.created_at.isoformat(),
            "action_url": notification.action_url,
            "action_text": notification.action_text,
            "content_type": (
                notification.content_type.app_label
                + "."
                + notification.content_type.model
                if notification.content_type
                else None
            ),
            "object_id": notification.object_id,
        }


class BulkNotificationConsumer(AsyncWebsocketConsumer):
    """
    Consumer for bulk notifications (admin/staff broadcasting).
    """

    async def connect(self):
        """Handle WebSocket connection."""
        self.user = self.scope["user"]

        # Check if user is authenticated and has permission
        if isinstance(self.user, AnonymousUser):
            await self.close()
            return

        # Check if user can send bulk notifications
        if not await self.can_send_bulk_notifications():
            await self.close()
            return

        # Join bulk notification group
        self.bulk_group_name = "bulk_notifications"
        await self.channel_layer.group_add(self.bulk_group_name, self.channel_name)

        await self.accept()

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        if hasattr(self, "bulk_group_name"):
            await self.channel_layer.group_discard(
                self.bulk_group_name, self.channel_name
            )

    async def receive(self, text_data):
        """Handle incoming bulk notification requests."""
        try:
            data = json.loads(text_data)
            message_type = data.get("type")

            if message_type == "send_bulk_notification":
                await self.handle_bulk_notification(data)

        except json.JSONDecodeError:
            await self.send(
                text_data=json.dumps(
                    {"type": "error", "message": "Invalid JSON format"}
                )
            )
        except Exception as e:
            await self.send(text_data=json.dumps({"type": "error", "message": str(e)}))

    async def handle_bulk_notification(self, data):
        """Handle sending bulk notifications."""
        title = data.get("title")
        message = data.get("message")
        notification_type = data.get("notification_type", "announcement")
        priority = data.get("priority", "medium")
        target_users = data.get("target_users", [])
        target_roles = data.get("target_roles", [])

        if not title or not message:
            await self.send(
                text_data=json.dumps(
                    {"type": "error", "message": "Title and message are required"}
                )
            )
            return

        # Get target users
        users = await self.get_target_users(target_users, target_roles)

        # Create notifications
        created_count = await self.create_bulk_notifications(
            users, notification_type, title, message, priority
        )

        # Send success response
        await self.send(
            text_data=json.dumps(
                {"type": "bulk_notification_sent", "count": created_count}
            )
        )

    @database_sync_to_async
    def can_send_bulk_notifications(self):
        """Check if user can send bulk notifications."""
        # Allow staff, teachers, and admins
        return (
            self.user.is_staff
            or hasattr(self.user, "teacher_profile")
            or self.user.is_superuser
        )

    @database_sync_to_async
    def get_target_users(self, target_user_ids, target_roles):
        """Get users based on target criteria."""
        from django.contrib.auth import get_user_model
        from apps.users.models import UserRole, Role

        User = get_user_model()
        users = User.objects.none()

        # Specific users
        if target_user_ids:
            users = users | User.objects.filter(id__in=target_user_ids)

        # Users by role
        if target_roles:
            role_users = User.objects.filter(
                user_roles__role__role_type__in=target_roles,
                user_roles__is_primary=True,
            )
            users = users | role_users

        # If no specific targets, send to all active users
        if not target_user_ids and not target_roles:
            users = User.objects.filter(is_active=True)

        return users.distinct()

    @database_sync_to_async
    def create_bulk_notifications(
        self, users, notification_type, title, message, priority
    ):
        """Create notifications for multiple users."""
        count = 0
        for user in users:
            # Resolve institution similar to other helpers
            try:
                from django.apps import apps

                Institution = apps.get_model("core", "Institution")
                inst = None
                primary = getattr(user, "institution_memberships", None)
                if primary and primary.filter(is_primary=True).exists():
                    inst = primary.filter(is_primary=True).first().institution
                elif getattr(user, "institutions", None) and user.institutions.exists():
                    inst = user.institutions.first()
                if not inst:
                    inst = Institution.objects.first()
            except Exception:
                inst = None

            RealTimeNotification.objects.create(
                recipient=user,
                notification_type=notification_type,
                title=title,
                message=message,
                priority=priority,
                institution=inst,
            )
            count += 1

            # Send real-time notification via WebSocket
            # This would be handled by the notification system
            # For now, we'll rely on the periodic task or manual triggering

        return count


class ChatConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time chat functionality.
    """

    async def connect(self):
        """Handle WebSocket connection."""
        self.user = self.scope["user"]
        self.room_id = self.scope["url_route"]["kwargs"]["room_id"]

        # Check if user is authenticated
        if isinstance(self.user, AnonymousUser):
            await self.close()
            return

        # Check if user has access to this room
        if not await self.can_access_room(self.room_id):
            await self.close()
            return

        # Join room group
        self.room_group_name = f"chat_{self.room_id}"
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        await self.accept()

        # Update user's last seen
        await self.update_last_seen()

        # Send recent messages
        await self.send_recent_messages()

        # Send room info
        await self.send_room_info()

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        # Leave room group
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(
                self.room_group_name, self.channel_name
            )

    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(text_data)
            message_type = data.get("type")

            if message_type == "chat_message":
                await self.handle_chat_message(data)
            elif message_type == "typing_start":
                await self.handle_typing_start()
            elif message_type == "typing_stop":
                await self.handle_typing_stop()
            elif message_type == "mark_read":
                await self.handle_mark_read(data)
            elif message_type == "edit_message":
                await self.handle_edit_message(data)
            elif message_type == "delete_message":
                await self.handle_delete_message(data)

        except json.JSONDecodeError:
            await self.send(
                text_data=json.dumps(
                    {"type": "error", "message": "Invalid JSON format"}
                )
            )
        except Exception as e:
            await self.send(text_data=json.dumps({"type": "error", "message": str(e)}))

    async def handle_chat_message(self, data):
        """Handle new chat message."""
        content = data.get("content", "").strip()
        reply_to_id = data.get("reply_to")

        if not content:
            return

        # Save message to database
        message = await self.save_message(content, reply_to_id)

        # Broadcast message to room
        await self.channel_layer.group_send(
            self.room_group_name,
            {"type": "chat_message", "message": await self.format_message(message)},
        )

    async def handle_typing_start(self):
        """Handle typing start indicator."""
        await self.update_typing_indicator(True)

        # Broadcast typing indicator
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "typing_indicator",
                "user": {
                    "id": self.user.id,
                    "name": self.user.get_full_name(),
                },
                "is_typing": True,
            },
        )

    async def handle_typing_stop(self):
        """Handle typing stop indicator."""
        await self.update_typing_indicator(False)

        # Broadcast typing indicator
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "typing_indicator",
                "user": {
                    "id": self.user.id,
                    "name": self.user.get_full_name(),
                },
                "is_typing": False,
            },
        )

    async def handle_mark_read(self, data):
        """Handle mark messages as read."""
        message_ids = data.get("message_ids", [])
        await self.mark_messages_read(message_ids)

    async def handle_edit_message(self, data):
        """Handle message editing."""
        message_id = data.get("message_id")
        new_content = data.get("content", "").strip()

        if not message_id or not new_content:
            return

        message = await self.edit_message(message_id, new_content)
        if message:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "message_edited",
                    "message": await self.format_message(message),
                },
            )

    async def handle_delete_message(self, data):
        """Handle message deletion."""
        message_id = data.get("message_id")

        if not message_id:
            return

        success = await self.delete_message(message_id)
        if success:
            await self.channel_layer.group_send(
                self.room_group_name,
                {"type": "message_deleted", "message_id": message_id},
            )

    # Event handlers for group messages
    async def chat_message(self, event):
        """Send chat message to WebSocket."""
        await self.send(
            text_data=json.dumps({"type": "message", "message": event["message"]})
        )

    async def typing_indicator(self, event):
        """Send typing indicator to WebSocket."""
        await self.send(text_data=json.dumps({"type": "typing", "data": event}))

    async def message_edited(self, event):
        """Send edited message to WebSocket."""
        await self.send(
            text_data=json.dumps(
                {"type": "message_edited", "message": event["message"]}
            )
        )

    async def message_deleted(self, event):
        """Send deleted message info to WebSocket."""
        await self.send(
            text_data=json.dumps(
                {"type": "message_deleted", "message_id": event["message_id"]}
            )
        )

    # Database operations
    @database_sync_to_async
    def can_access_room(self, room_id):
        """Check if user can access the room."""
        try:
            room = ChatRoom.objects.get(id=room_id, is_active=True)
            return room.members.filter(id=self.user.id).exists()
        except ChatRoom.DoesNotExist:
            return False

    @database_sync_to_async
    def save_message(self, content, reply_to_id=None):
        """Save message to database."""
        reply_to = None
        if reply_to_id:
            try:
                reply_to = ChatMessage.objects.get(id=reply_to_id)
            except ChatMessage.DoesNotExist:
                pass

        return ChatMessage.objects.create(
            room_id=self.room_id, sender=self.user, content=content, reply_to=reply_to
        )

    @database_sync_to_async
    def update_last_seen(self):
        """Update user's last seen timestamp."""
        ChatParticipant.objects.filter(room_id=self.room_id, user=self.user).update(
            last_seen_at=timezone.now()
        )

    @database_sync_to_async
    def update_typing_indicator(self, is_typing):
        """Update typing indicator."""
        if is_typing:
            TypingIndicator.objects.update_or_create(
                room_id=self.room_id,
                user=self.user,
                defaults={"timestamp": timezone.now()},
            )
        else:
            TypingIndicator.objects.filter(
                room_id=self.room_id, user=self.user
            ).delete()

    @database_sync_to_async
    def send_recent_messages(self):
        """Send recent messages to the user."""
        messages = (
            ChatMessage.objects.filter(room_id=self.room_id)
            .select_related("sender", "sender__profile")
            .order_by("-created_at")[:50][::-1]
        )

        for message in messages:
            formatted_message = await self.format_message(message)
            await self.send(
                text_data=json.dumps({"type": "message", "message": formatted_message})
            )

    @database_sync_to_async
    def send_room_info(self):
        """Send room information."""
        try:
            room = ChatRoom.objects.get(id=self.room_id)
            participants = ChatParticipant.objects.filter(room=room).select_related(
                "user", "user__profile"
            )

            room_data = {
                "id": room.id,
                "name": room.name,
                "description": room.description,
                "room_type": room.room_type,
                "member_count": room.member_count,
                "participants": [
                    {
                        "id": p.user.id,
                        "name": p.user.get_full_name(),
                        "avatar": (
                            p.user.profile.profile_picture.url
                            if p.user.profile and p.user.profile.profile_picture
                            else None
                        ),
                        "role": p.role,
                        "last_seen": p.last_seen_at.isoformat(),
                    }
                    for p in participants
                ],
            }

            await self.send(
                text_data=json.dumps({"type": "room_info", "room": room_data})
            )

        except ChatRoom.DoesNotExist:
            pass

    @database_sync_to_async
    def mark_messages_read(self, message_ids):
        """Mark messages as read."""
        messages = ChatMessage.objects.filter(id__in=message_ids, room_id=self.room_id)
        for message in messages:
            message.mark_as_read(self.user)

    @database_sync_to_async
    def edit_message(self, message_id, new_content):
        """Edit a message."""
        try:
            message = ChatMessage.objects.get(
                id=message_id, room_id=self.room_id, sender=self.user
            )
            message.content = new_content
            message.is_edited = True
            message.edited_at = timezone.now()
            message.save()
            return message
        except ChatMessage.DoesNotExist:
            return None

    @database_sync_to_async
    def delete_message(self, message_id):
        """Delete a message."""
        try:
            message = ChatMessage.objects.get(
                id=message_id, room_id=self.room_id, sender=self.user
            )
            message.delete()
            return True
        except ChatMessage.DoesNotExist:
            return False

    @database_sync_to_async
    def format_message(self, message):
        """Format message for WebSocket transmission."""
        return {
            "id": message.id,
            "content": message.content,
            "message_type": message.message_type,
            "sender": {
                "id": message.sender.id,
                "name": message.sender.get_full_name(),
                "avatar": (
                    message.sender.profile.profile_picture.url
                    if message.sender.profile and message.sender.profile.profile_picture
                    else None
                ),
            },
            "timestamp": message.created_at.isoformat(),
            "is_edited": message.is_edited,
            "edited_at": message.edited_at.isoformat() if message.edited_at else None,
            "reply_to": message.reply_to.id if message.reply_to else None,
            "is_read": message.is_read_by_user(self.user),
        }
