"""Django Admin configuration for shared/global resources.

Domain apps register their own models in their own ``admin.py``; this
module only customizes the shared admin site chrome (PRD: interface in
Brazilian Portuguese).
"""

from django.contrib import admin

admin.site.site_header = "Sistema de Gestão para Dog Walker Inteligente"
admin.site.site_title = "Sistema de Gestão para Dog Walker Inteligente"
admin.site.index_title = "Administração"
