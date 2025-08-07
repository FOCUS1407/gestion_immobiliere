from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Sum, F, Case, When, DecimalField
from .models import Paiement


def get_financial_summary(year, month):
    """
    Calcule le résumé financier pour un mois et une année donnés en une seule requête.
    Retourne un dictionnaire avec le total attendu, payé, impayé et la commission.
    """
    # Utilise l'agrégation conditionnelle pour tout calculer en une seule requête.
    # C'est beaucoup plus performant que de multiples requêtes et des boucles en Python.
    summary = Paiement.objects.filter(
        date_paiement__year=year,
        date_paiement__month=month
    ).aggregate(
        total_attendu=Sum('montant_attendu', default=0),
        total_paye=Sum(
            Case(When(statut='paye', then='montant_paye'), default=0, output_field=DecimalField())
        ),
        # La commission est calculée sur le montant payé en utilisant le taux du propriétaire associé.
        # Les expressions F() permettent de faire référence à des champs de modèles liés dans la requête.
        total_commission=Sum(
            Case(
                When(statut='paye', then=F('montant_paye') * F('location__chambre__immeuble__proprietaire__taux_commission') / 100),
                default=0,
                output_field=DecimalField()
            )
        )
    )

    total_attendu = summary.get('total_attendu') or 0
    total_paye = summary.get('total_paye') or 0
    commission = summary.get('total_commission') or 0

    return {
        'total_attendu_mois': total_attendu,
        'total_paye_mois': total_paye,
        'total_impaye_mois': total_attendu - total_paye,
        'commission_mois': commission,
    }

def paginate_queryset(request, queryset, page_size, page_param='page'):
    """Factorise la logique de pagination pour éviter la répétition de code."""
    paginator = Paginator(queryset, page_size)
    page_number = request.GET.get(page_param, 1)
    try:
        return paginator.page(page_number)
    except (PageNotAnInteger, EmptyPage):
        return paginator.page(1)