"""
GIT WORKFLOW - PokéAlert

Este documento describe las mejores prácticas para trabajar con git
en el proyecto PokéAlert.

## Configuración Inicial

### 1. Clonar el repositorio

```bash
git clone https://github.com/tu-usuario/pokealert.git
cd pokealert
```

### 2. Configurar git hooks automáticos (RECOMENDADO)

```bash
git config core.hooksPath .githooks
chmod +x .githooks/pre-commit
```

Esto asegura que antes de cada commit se validen:
- Formato de código (Black)
- Estilo (Flake8)
- Docstrings (Pydocstyle)

### 3. Configurar usuario de git

```bash
git config user.name "Tu Nombre"
git config user.email "tu.email@example.com"
```

## Flujo de Desarrollo

### Opción A: Con Pre-commit Hooks (RECOMENDADO)

```bash
# 1. Crear rama feature
git checkout -b feature/nueva-funcionalidad

# 2. Realizar cambios
# ... edita archivos ...

# 3. Staging de cambios
git add cards/views.py alerts/models.py  # Específicos
# O todo:
git add .

# 4. Git intent: pre-commit hook valida automáticamente
git commit -m "Agrega nueva funcionalidad en cards"
# ↓ Se ejecutan automáticamente:
#   - black (formatea código)
#   - flake8 (valida estilo)
#   - pydocstyle (valida docstrings)
# Si algo falla, el commit se cancela

# 5. Si hay errores, corrígelos y reinténtalo
python validate.py --fix  # Arregla automáticamente
git add .
git commit -m "Agrega nueva funcionalidad en cards"

# 6. Push a la rama
git push origin feature/nueva-funcionalidad

# 7. Abrir Pull Request en GitHub
```

### Opción B: Sin Pre-commit Hooks

```bash
# 1. Crear rama feature
git checkout -b feature/nueva-funcionalidad

# 2. Realizar cambios
# ... edita archivos ...

# 3. ANTES de commit, validar manualmente
python validate.py

# Si hay errores:
python validate.py --fix

# 4. Staging
git add .

# 5. Commit (sin validación automática)
git commit -m "Agrega nueva funcionalidad en cards"

# 6. Push
git push origin feature/nueva-funcionalidad

# 7. Pull Request
```

## Convenciones de Commits

### Mensaje de commit

Usa formato claro y descriptivo:

```
tipo: descripción breve (50 caracteres máximo)

Descripción más detallada si es necesario (72 caracteres por línea).
Explica QUÉ cambió y POR QUÉ.

Fixes: #123  (si cierra un issue)
```

### Tipos de commit

```
feat:     Nueva funcionalidad
fix:      Corrección de bug
docs:     Cambios en documentación
style:    Formateo, sin cambios de lógica
refactor: Refactorización de código
test:     Agregar o actualizar tests
chore:    Cambios en dependencias, build, etc
```

### Ejemplos

```
feat: agregar búsqueda por artista en cartas

El usuario puede ahora filtrar cartas por artista.
Se agregó campo 'artist_filter' a la búsqueda avanzada.

Fixes: #42

---

fix: corregir gráfico de precios no actualizando

El problema era que la caché no se invalidaba después de
agregar un nuevo PriceHistory. Ahora se invalida correctamente.

---

docs: actualizar guía de instalación

Agregué pasos para configurar Redis en Windows.

---

test: agregar cobertura para PriceAlert.create()

Se agregaron 3 nuevos casos de test para validar
la creación de alertas con diferentes parámetros.
```

## Branching Strategy

### Ramas principales

```
main/master     - Código en producción (releases)
develop         - Código de desarrollo (staging)
feature/*       - Nuevas características
fix/*           - Correcciones de bugs
docs/*          - Cambios en documentación
```

### Flujo (Git Flow)

```
main
 ↑
 │ (merge pull request)
 ├─ develop
     ↑
     │ (merge pull request)
     ├─ feature/nueva-funcionalidad
     ├─ fix/bug-critico
     └─ docs/actualizar-readme
```

## Gestión de .env

**¡CRÍTICO: NUNCA comitees `.env` con datos reales!**

```bash
# ✓ CORRECTO - Usar .env.example como plantilla
cp .env.example .env
# Editar .env con valores locales

# El archivo .env está en .gitignore y no se comiteará

# Si necesitas actualizar .env.example (SIN SECRETOS):
git add .env.example
git commit -m "docs: actualizar .env.example con nueva variable"
```

## Limpieza de ramas

```bash
# Ver ramas locales
git branch

# Ver ramas remotas
git branch -r

# Eliminar rama local
git branch -d feature/funcionalidad-vieja

# Eliminar rama remota
git push origin --delete feature/funcionalidad-vieja

# Limpiar referencias muertas
git remote prune origin
```

## Útiles

### Ver historial

```bash
git log --oneline --graph --all
git log --grep="fix"  # Buscar commits
```

### Deshacer cambios

```bash
# Deshacer cambios no staged
git restore archivo.py
# O: git checkout -- archivo.py

# Deshacer commit local (sin perder cambios)
git reset --soft HEAD~1

# Ver qué cambió
git diff
git diff --cached  # Cambios staged
```

### Stash (guardar cambios temporales)

```bash
# Guardar cambios sin hacer commit
git stash

# Ver stash guardados
git stash list

# Recuperar último stash
git stash pop
```

## Troubleshooting

### "Your branch is ahead of 'origin/main' by 2 commits"

```bash
# Has hecho commits locales. Puedes:

# Opción 1: Push (recomendado)
git push origin feature/mi-rama

# Opción 2: Reset (cuidado, perderás cambios)
git reset --hard origin/main
```

### "Merge conflict"

```bash
# Si hay conflicto al mergear:
# 1. Edita el archivo conflictivo
# 2. Resuelve los conflictos (busca <<<<<<, ======, >>>>>>)
# 3. Guarda los cambios
# 4. Completa el merge
git add archivo-conflictivo.py
git commit -m "Resolve merge conflict"
```

### "I committed to the wrong branch"

```bash
# Si cometiste a main en lugar de a feature/:

# 1. Guarda el commit
git log --oneline -n 1  # Nota el hash: abc123

# 2. Reset main
git reset --hard origin/main

# 3. Crea/cambia a la rama correcta
git checkout -b feature/mi-rama

# 4. Cherry-pick el commit
git cherry-pick abc123
```

## GitHub / GitLab Workflow (Pull Request)

1. **Crear rama feature**
   ```bash
   git checkout -b feature/nueva-funcionalidad
   ```

2. **Hacer cambios y commits**
   ```bash
   git add .
   git commit -m "feat: agrega funcionalidad"
   ```

3. **Push a remoto**
   ```bash
   git push origin feature/nueva-funcionalidad
   ```

4. **Abrir Pull Request en GitHub/GitLab**
   - Título: "Agrega búsqueda por artista"
   - Descripción: Explica qué hace, cómo probarlo, qué cierra
   - Asigna reviewers

5. **Esperar aprobación y CI/CD**
   - GitHub Actions / GitLab CI valida automáticamente
   - Reviewers revisan el código
   - Resolves comentarios si hay

6. **Merge a develop**
   ```bash
   # GitHub/GitLab: click "Merge pull request"
   ```

7. **Eliminar rama**
   ```bash
   git branch -d feature/nueva-funcionalidad
   git push origin --delete feature/nueva-funcionalidad
   ```

## Mejores Prácticas

✓ **DO**
- ✓ Hacer commits pequeños y frecuentes (una funcionalidad por commit)
- ✓ Escribir mensajes de commit descriptivos
- ✓ Crear ramas para cada feature (no commits directos a main)
- ✓ Validar código antes de commit (usar validate.py)
- ✓ Revisar cambios antes de push (git diff)
- ✓ Sincronizar con main regularmente (git pull)

✗ **DON'T**
- ✗ Commitear .env, db.sqlite3, o archivos personales
- ✗ Pushear directamente a main/develop
- ✗ Hacer commits grandes con múltiples cambios no relacionados
- ✗ Commitar archivos sin pasar validación
- ✗ Reescribir historial en ramas compartidas (git push --force)
- ✗ Ignorar advertencias de pre-commit hooks

"""
