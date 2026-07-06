from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import UserUpdateForm
from alerts.models import PriceAlert


@login_required
def profile(request):
    if request.method == "POST":
        form = UserUpdateForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            request.session['pokemon_avatar'] = form.cleaned_data['pokemon_avatar']
            messages.success(request, "¡Tu perfil de Entrenador se ha actualizado!")
            return redirect("profile")
    else:
        initial_avatar = request.session.get('pokemon_avatar', 'pikachu')
        form = UserUpdateForm(instance=request.user, initial={'pokemon_avatar': initial_avatar})

    total_alertas = PriceAlert.objects.filter(user=request.user).count()

    if total_alertas >= 5:
        rango = "Maestro TCG"
    elif total_alertas >= 2:
        rango = "Coleccionista"
    else:
        rango = "Novato"

    avatar_urls = {
        'pikachu': 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/25.png',
        'charizard': 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/6.png',
        'gengar': 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/94.png',
        'mewtwo': 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/150.png',
        'lugia': 'https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/249.png',
    }
    
    current_avatar_url = avatar_urls.get(request.session.get('pokemon_avatar', 'pikachu'))

    context = {
        "form": form,
        "avatar_url": current_avatar_url,
        "total_alertas": total_alertas,
        "rango": rango,
    }

    return render(request, "users/profile.html", context)