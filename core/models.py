import random
import string
from django.db import models

def generate_room_code():
    """Generates a unique random 6-character room code."""
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        if not Room.objects.filter(code=code).exists():
            return code

class Room(models.Model):
    """Represents a game room."""
    STATUS_PREDICTING = 'predicting'
    STATUS_LOCKED = 'locked'
    STATUS_RESULTS = 'results'
    STATUS_CHOICES = [
        (STATUS_PREDICTING, 'Prediciendo'),
        (STATUS_LOCKED, 'Bloqueado'),
        (STATUS_RESULTS, 'Resultados'),
    ]

    code = models.CharField(max_length=6, unique=True, default=generate_room_code)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PREDICTING)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Sala {self.code}"

class Participant(models.Model):
    """Represents a user in a room."""
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='participants')
    name = models.CharField(max_length=50)
    is_admin = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('room', 'name')

    def __str__(self):
        return f"{self.name} en {self.room.code}"

class Assignment(models.Model):
    """Represents the actual secret santa assignments."""
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='assignments')
    giver = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name='giving_to')
    receiver = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name='receiving_from')

    class Meta:
        unique_together = ('room', 'giver')

    def __str__(self):
        return f"{self.giver.name} -> {self.receiver.name} ({self.room.code})"

class Prediction(models.Model):
    """Represents a user's prediction."""
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='predictions')
    user = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name='predictions_made')
    predicted_giver = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name='predicted_as_giver')
    predicted_receiver = models.ForeignKey(Participant, on_delete=models.CASCADE, related_name='predicted_as_receiver')
    
    class Meta:
        unique_together = ('user', 'predicted_receiver')

    def __str__(self):
        return f"Predicción de {self.user.name}: {self.predicted_giver.name} -> {self.predicted_receiver.name}"