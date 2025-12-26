from django.shortcuts import render, redirect
from django.urls import reverse
from .models import Room, Participant, Prediction, generate_room_code, Assignment
from django.contrib import messages
from django.db.models import Count
import random

def home_view(request):
    """
    Handles the home page, allowing users to create or join a room.
    """
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create_room':
            room_code = generate_room_code()
            new_room = Room.objects.create(code=room_code)
            
            # The user who creates the room is the admin and the first participant
            participant_name = request.POST.get('admin_name', 'Admin') # Default name for admin
            new_participant = Participant.objects.create(
                room=new_room,
                name=participant_name,
                is_admin=True
            )

            request.session['room_code'] = new_room.code
            request.session['participant_id'] = new_participant.id
            request.session['is_admin'] = True
            
            messages.success(request, f"Sala '{new_room.code}' creada con éxito. ¡Eres el administrador!")
            return redirect(reverse('core:dashboard'))

        elif action == 'join_room':
            room_code = request.POST.get('room_code', '').upper()
            try:
                room = Room.objects.get(code=room_code)
                request.session['room_code'] = room.code
                request.session['is_admin'] = False # Reset admin status for new joiners
                # Redirect to choose name if room exists
                return redirect(reverse('core:choose_name'))
            except Room.DoesNotExist:
                messages.error(request, "Código de sala no válido.")
                return redirect(reverse('core:home'))

    return render(request, 'core/home.html')

def choose_name_view(request):
    """
    Allows a user to choose their name for a room after joining.
    """
    room_code = request.session.get('room_code')
    if not room_code:
        messages.error(request, "No hay sala seleccionada. Por favor, únete a una sala primero.")
        return redirect(reverse('core:home'))

    room = Room.objects.get(code=room_code)

    if request.method == 'POST':
        participant_name = request.POST.get('name', '').strip()
        if not participant_name:
            messages.error(request, "Por favor, introduce un nombre.")
        elif Participant.objects.filter(room=room, name=participant_name).exists():
            messages.error(request, f"El nombre '{participant_name}' ya está en uso en esta sala. Elige otro.")
        else:
            new_participant = Participant.objects.create(room=room, name=participant_name, is_admin=False)
            request.session['participant_id'] = new_participant.id
            messages.success(request, f"¡Bienvenido, {participant_name}!")
            
            return redirect(reverse('core:dashboard'))
    
    return render(request, 'core/choose_name.html', {'room_code': room_code})

def dashboard_view(request):
    """
    Displays the main dashboard for a participant in a room.
    """
    room_code = request.session.get('room_code')
    participant_id = request.session.get('participant_id')

    if not room_code or not participant_id:
        messages.error(request, "No estás en ninguna sala. Por favor, únete o crea una.")
        return redirect(reverse('core:home'))

    try:
        room = Room.objects.get(code=room_code)
        participant = Participant.objects.get(id=participant_id, room=room)
    except (Room.DoesNotExist, Participant.DoesNotExist):
        # Session data is invalid, clear it
        if 'room_code' in request.session:
            del request.session['room_code']
        if 'participant_id' in request.session:
            del request.session['participant_id']
        if 'is_admin' in request.session:
            del request.session['is_admin']
        messages.error(request, "Tu sesión ha expirado o es inválida.")
        return redirect(reverse('core:home'))
    
    total_participants = room.participants.count()
    # A user makes a prediction for each participant, including themselves (who gifts to me?)
    required_predictions_per_user = total_participants

    # Count all predictions made by this user in this room
    completed_predictions_count = Prediction.objects.filter(
        room=room,
        user=participant
    ).count()

    # Determine if predictions are 'sent' by checking if all required predictions are made
    predictions_sent = completed_predictions_count == required_predictions_per_user
    
    context = {
        'room': room,
        'participant': participant,
        'is_admin': request.session.get('is_admin', False),
        'total_participants': total_participants,
        'participants_list': list(room.participants.values_list('name', flat=True)),
        'completed_predictions_count': completed_predictions_count,
        'required_predictions_per_user': required_predictions_per_user,
        'predictions_sent': predictions_sent,
    }
    return render(request, 'core/dashboard.html', context)

def prediction_view(request):
    """
    Allows a participant to make predictions for who gives gifts to whom.
    """
    room_code = request.session.get('room_code')
    participant_id = request.session.get('participant_id')

    if not room_code or not participant_id:
        messages.error(request, "No estás en ninguna sala. Por favor, únete o crea una.")
        return redirect(reverse('core:home'))

    try:
        room = Room.objects.get(code=room_code)
        current_participant = Participant.objects.get(id=participant_id, room=room)
    except (Room.DoesNotExist, Participant.DoesNotExist):
        if 'room_code' in request.session: del request.session['room_code']
        if 'participant_id' in request.session: del request.session['participant_id']
        if 'is_admin' in request.session: del request.session['is_admin']
        messages.error(request, "Tu sesión ha expirado o es inválida.")
        return redirect(reverse('core:home'))

    if room.status != Room.STATUS_PREDICTING:
        messages.warning(request, "Las predicciones están bloqueadas o los resultados ya han sido revelados.")
        return redirect(reverse('core:dashboard'))

    # Participants for whom the current user will make predictions (everyone, including themselves to predict their giver)
    receivers_to_predict_for = room.participants.all().order_by('name')
    # All participants to choose as givers
    possible_givers = room.participants.order_by('name')

    # Fetch existing predictions for the current user
    user_predictions = Prediction.objects.filter(
        room=room,
        user=current_participant
    ).select_related('predicted_giver', 'predicted_receiver')

    # Organize existing predictions for easy template access
    predictions_map = {p.predicted_receiver.id: p.predicted_giver.id for p in user_predictions}

    if request.method == 'POST':
        # Check if the "confirm_all" button was pressed
        if 'confirm_all' in request.POST:
            # Logic to "lock" predictions for this user could go here
            # For now, simply saving them is sufficient.
            messages.success(request, "¡Tus predicciones han sido enviadas!")
            # Optionally change status of participant or add a flag
            return redirect(reverse('core:dashboard'))
        
        # Handle individual prediction submissions
        for receiver in receivers_to_predict_for:
            predicted_giver_id = request.POST.get(f'giver_for_{receiver.id}')
            
            if predicted_giver_id:
                try:
                    predicted_giver = Participant.objects.get(id=predicted_giver_id, room=room)
                    
                    # Ensure no one predicts themselves as giver for someone
                    # This rule applies to the actual assignment, not necessarily prediction validation,
                    # but good to guide user away from impossible choices.
                    # For now, just save. More robust validation can be added.

                    Prediction.objects.update_or_create(
                        room=room,
                        user=current_participant,
                        predicted_receiver=receiver,
                        defaults={'predicted_giver': predicted_giver}
                    )
                except Participant.DoesNotExist:
                    messages.error(request, f"Error al procesar la predicción para {receiver.name}.")
                    # Continue to try and save other valid predictions
        messages.success(request, "Predicciones guardadas.")
        return redirect(reverse('core:prediction')) # Stay on prediction page to allow more edits or see updates

    context = {
        'room': room,
        'current_participant': current_participant,
        'receivers_to_predict_for': receivers_to_predict_for,
        'possible_givers': possible_givers,
        'predictions_map': predictions_map,
    }
    return render(request, 'core/prediction.html', context)


def admin_dashboard_view(request):
    """
    Admin panel for the room. Only accessible by the room admin.
    Allows generation of assignments, blocking predictions, and enabling results.
    """
    room_code = request.session.get('room_code')
    participant_id = request.session.get('participant_id')
    is_admin = request.session.get('is_admin', False)

    if not room_code or not participant_id or not is_admin:
        messages.error(request, "Acceso denegado. Solo los administradores pueden ver este panel.")
        return redirect(reverse('core:home'))

    try:
        room = Room.objects.get(code=room_code)
        # Ensure the participant is indeed the admin of this room
        participant = Participant.objects.get(id=participant_id, room=room, is_admin=True) 
    except (Room.DoesNotExist, Participant.DoesNotExist):
        # Session data is invalid, clear it
        if 'room_code' in request.session: del request.session['room_code']
        if 'participant_id' in request.session: del request.session['participant_id']
        if 'is_admin' in request.session: del request.session['is_admin']
        messages.error(request, "Tu sesión ha expirado o no tienes permisos de administrador.")
        return redirect(reverse('core:home'))
    
    # Logic for admin actions (POST requests)
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'generate_assignments':
            participants_in_room = list(room.participants.all())
            if len(participants_in_room) < 2:
                messages.error(request, "Necesitas al menos 2 participantes para generar el sorteo.")
            else:
                # Clear existing assignments first
                room.assignments.all().delete()

                givers = list(participants_in_room)
                receivers = list(participants_in_room)
                random.shuffle(givers)
                random.shuffle(receivers)

                assignments = []
                # Simple iterative assignment
                for i in range(len(givers)):
                    giver = givers[i]
                    receiver = receivers[i]
                    
                    # Ensure no one gifts themselves, and try to prevent direct cycles in simple cases
                    # This simplified logic might still lead to unsolvable cases or cycles in larger groups
                    # but is a good start for a basic implementation.
                    attempts = 0
                    while giver == receiver or (len(givers) > 2 and Assignment.objects.filter(room=room, giver=receiver, receiver=giver).exists()):
                        random.shuffle(receivers)
                        receiver = receivers[i % len(receivers)] # Use modulo to stay within bounds
                        attempts += 1
                        if attempts > len(givers) * len(givers): # Limit attempts to prevent infinite loop
                            messages.error(request, "No se pudo generar un sorteo válido. Intenta de nuevo o ajusta los participantes.")
                            return redirect(reverse('core:admin_dashboard'))

                    Assignment.objects.create(room=room, giver=giver, receiver=receiver)
                messages.success(request, "¡Sorteo generado con éxito!")

        elif action == 'lock_predictions':
            if room.status != Room.STATUS_PREDICTING:
                messages.warning(request, "Las predicciones ya están bloqueadas o los resultados habilitados.")
            else:
                room.status = Room.STATUS_LOCKED
                room.save()
                messages.success(request, "Predicciones bloqueadas.")
        elif action == 'enable_results':
            if room.status == Room.STATUS_RESULTS:
                messages.warning(request, "Los resultados ya están habilitados.")
            elif not room.assignments.exists():
                messages.error(request, "Primero debes generar el sorteo para habilitar los resultados.")
            else:
                room.status = Room.STATUS_RESULTS
                room.save()
                messages.success(request, "Resultados habilitados.")
        elif action == 'manual_assign_givers':
            participants_in_room = list(room.participants.all())
            if len(participants_in_room) < 2:
                messages.error(request, "Necesitas al menos 2 participantes para realizar asignaciones manuales.")
                return redirect(reverse('core:admin_dashboard'))

            manual_assignments_data = {} # {receiver_id: giver_id}
            for receiver in participants_in_room:
                giver_id = request.POST.get(f'giver_for_manual_{receiver.id}')
                if not giver_id:
                    messages.error(request, f"Debes seleccionar un amigo secreto para {receiver.name}.")
                    return redirect(reverse('core:admin_dashboard'))
                
                try:
                    giver = Participant.objects.get(id=giver_id, room=room)
                    manual_assignments_data[receiver.id] = giver.id
                except Participant.DoesNotExist:
                    messages.error(request, f"Amigo secreto seleccionado para {receiver.name} no es válido.")
                    return redirect(reverse('core:admin_dashboard'))
            
            # --- Validation for manual assignments ---
            assigned_givers = set(manual_assignments_data.values())
            if len(assigned_givers) != len(participants_in_room):
                messages.error(request, "Cada participante debe dar un regalo a una persona diferente, y cada persona debe recibir solo de una persona.")
                return redirect(reverse('core:admin_dashboard'))

            for receiver_id, giver_id in manual_assignments_data.items():
                if receiver_id == giver_id:
                    receiver_name = Participant.objects.get(id=receiver_id).name
                    messages.error(request, f"{receiver_name} no puede regalarse a sí mismo.")
                    return redirect(reverse('core:admin_dashboard'))
            
            # Clear existing assignments before creating new ones
            room.assignments.all().delete()
            
            # Create new assignments based on manual input
            for receiver_id, giver_id in manual_assignments_data.items():
                receiver = Participant.objects.get(id=receiver_id, room=room)
                giver = Participant.objects.get(id=giver_id, room=room)
                Assignment.objects.create(room=room, giver=giver, receiver=receiver)
            
            # Set room status to results if it's not already
            if room.status != Room.STATUS_RESULTS:
                room.status = Room.STATUS_RESULTS
                room.save()

            messages.success(request, "¡Asignaciones manuales guardadas con éxito! Los resultados están habilitados.")
            return redirect(reverse('core:admin_dashboard'))


    # Prepare actual assignments for pre-selection in the manual assignment form
    actual_assignments_display = []
    current_assignments = room.assignments.all()
    for assign in current_assignments:
        actual_assignments_display.append({
            'giver_id': assign.giver.id,
            'receiver_id': assign.receiver.id,
        })

    context = {
        'room': room,
        'participant': participant, # This is the admin participant
        'all_participants': room.participants.all().order_by('name'), # All participants for display
        'room_status_display': room.get_status_display(),
        'assignments_exist': room.assignments.exists(),
        'actual_assignments_display': actual_assignments_display, # Pass to template for pre-selection
    }
    return render(request, 'core/admin_dashboard.html', context)


def results_view(request):
    """
    Displays the results of the Secret Santa draw and the prediction ranking.
    """
    room_code = request.session.get('room_code')
    participant_id = request.session.get('participant_id')

    if not room_code or not participant_id:
        messages.error(request, "No estás en ninguna sala. Por favor, únete o crea una.")
        return redirect(reverse('core:home'))

    try:
        room = Room.objects.get(code=room_code)
        current_participant = Participant.objects.get(id=participant_id, room=room)
    except (Room.DoesNotExist, Participant.DoesNotExist):
        if 'room_code' in request.session: del request.session['room_code']
        if 'participant_id' in request.session: del request.session['participant_id']
        if 'is_admin' in request.session: del request.session['is_admin']
        messages.error(request, "Tu sesión ha expirado o es inválida.")
        return redirect(reverse('core:home'))
    
    if room.status != Room.STATUS_RESULTS:
        messages.warning(request, "Los resultados aún no han sido habilitados por el administrador.")
        return redirect(reverse('core:dashboard'))

    # --- Winner Calculation Logic ---
    participants_in_room = room.participants.all()
    all_assignments = Assignment.objects.filter(room=room).select_related('giver', 'receiver')
    all_predictions = Prediction.objects.filter(room=room).select_related('user', 'predicted_giver', 'predicted_receiver')

    # Build a map of actual assignments: {giver_id: receiver_id}
    assignment_map = {assignment.giver.id: assignment.receiver.id for assignment in all_assignments}

    # Initialize scores for all participants
    scores = {p.name: {'score': 0, 'predictions': []} for p in participants_in_room}

    # Calculate scores
    for prediction in all_predictions:
        # Check if the predicted assignment matches the actual assignment
        # A prediction is correct if:
        # 1. The predicted receiver is actually receiving from the predicted giver
        # 2. AND the user made a prediction for *this specific* receiver
        
        # Does this predicted receiver exist in the actual assignments?
        actual_receiver_for_predicted_giver = assignment_map.get(prediction.predicted_giver.id)

        is_correct_prediction = (
            actual_receiver_for_predicted_giver == prediction.predicted_receiver.id
        )

        if is_correct_prediction:
            scores[prediction.user.name]['score'] += 1
        
        scores[prediction.user.name]['predictions'].append({
            'predicted_giver': prediction.predicted_giver.name,
            'predicted_receiver': prediction.predicted_receiver.name,
            'is_correct': is_correct_prediction,
        })
    
    # Sort participants by score (descending)
    ranking = sorted(scores.items(), key=lambda item: item[1]['score'], reverse=True)

    # Determine winner(s)
    winners = []
    if ranking:
        max_score = ranking[0][1]['score']
        for name, data in ranking:
            if data['score'] == max_score:
                winners.append(name)

    # Prepare actual assignments for display (if admin)
    actual_assignments_display = []
    for assign in all_assignments:
        actual_assignments_display.append({
            'giver': assign.giver.name,
            'receiver': assign.receiver.name,
        })


    context = {
        'room': room,
        'current_participant': current_participant,
        'ranking': ranking,
        'winners': winners,
        'actual_assignments': actual_assignments_display if current_participant.is_admin else [],
        'show_actual_assignments': current_participant.is_admin,
    }
    return render(request, 'core/results.html', context)