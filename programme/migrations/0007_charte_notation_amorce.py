# Amorce la charte de notation FAHIMTANA avec le contenu déjà en vigueur
# dans le projet (CHARTE_NOTATION_v2.md à la racine du dépôt), complété par
# les règles de style rédactionnel utilisées pour la construction des
# prompts IA. Contenu recopié en dur ICI plutôt qu'importé depuis le code
# applicatif : une migration ne doit jamais dépendre d'un module qui peut
# changer par la suite (voir doc Django sur les migrations de données).
#
# Éditable ensuite depuis l'admin Django (Programme > Chartes de notation).

from django.db import migrations

CONTENU_INITIAL = r"""# Charte de notation mathématique — FAHIMTANA

> **Règle d'or :** l'élève retrouve dans chaque leçon les notations exactes
> de son cours et de ses manuels. Convention **nigérienne / francophone**,
> jamais les variantes anglo-saxonnes. Toutes les formules en **LaTeX**
> (rendu KaTeX).

---

## A. Style rédactionnel

- 90 % du temps : on **rédige et on explique**, on paraphrase — on ne
  bombarde pas l'élève de formules brutes sans phrases autour. Les formules
  ponctuent un propos déjà clair en prose.
- Formules affichées (display) : le `$$` ouvrant seul sur sa ligne, la
  formule sur la ligne suivante, puis `$$` seul sur sa propre ligne. Sinon
  KaTeX ne centre pas correctement le rendu.
  ```
  $$
  \int_a^b f(x)\,dx
  $$
  ```
- Formules courtes en ligne : `$...$` directement dans la phrase.

## B. Ensembles de nombres

Notation : ℕ ℤ ℚ ℝ ℂ → LaTeX `\mathbb{N} \mathbb{Z} \mathbb{Q} \mathbb{R} \mathbb{C}`.
Variantes : `\mathbb{R}^*`, `\mathbb{R}_+`, `\mathbb{R}_+^*`,
`\mathbb{R} \setminus \{1\}`, `\mathbb{Z}/n\mathbb{Z}`.
**Jamais** `ZZ`, `RR`, ni le gras pour un ensemble.

## C. Vecteurs — flèche impérative

`\vec{u}`, `\overrightarrow{AB}`, norme `\|\overrightarrow{AB}\|`, produit
scalaire `\vec{u} \cdot \vec{v}`. **Jamais** le gras pour un vecteur.

## D. Intervalles — convention française

| ✅ | LaTeX | ❌ anglo |
|----|-------|----------|
| ]a,b[ | `]a,\,b[` | `(a,b)` |
| [a,b] | `[a,\,b]` | |
| [a,b[ | `[a,\,b[` | |
| ]-∞,a] | `]-\infty,\,a]` | |

## E. Logique et quantificateurs

`\forall`, `\exists`, `\Rightarrow`, `\Leftrightarrow`, `\in`, `\notin`,
`\subset`, `\cup`, `\cap`, `\emptyset`, `\setminus`.

## F. Par domaine (programme de Terminale C)

**Arithmétique** — congruence `a \equiv b \pmod{n}` ; PGCD/PPCM **en toutes
lettres** `\mathrm{PGCD}(a,b)` / `\mathrm{PPCM}(a,b)` (jamais `\gcd` ni
`\mathrm{lcm}`) ; divise `a \mid b`, ne divise pas `a \nmid b` ; premiers
entre eux `a \wedge b = 1`.

**Nombres complexes** — forme algébrique `z = a + ib` (lettre **i**, jamais
`j`) ; conjugué `\bar{z}` ; module `|z|` ; argument `\arg(z)` ; forme
trigonométrique `z = r(\cos\theta + i\sin\theta)` ; forme exponentielle
`z = r\,e^{i\theta}` ; affixe `z_A` ; `\mathrm{Re}(z)`, `\mathrm{Im}(z)`.

**Géométrie (barycentres, applications affines, coniques)** — barycentre
`G = \mathrm{bar}\{(A_i,\alpha_i)\}` ; relation vectorielle
`\sum \alpha_i\,\overrightarrow{GA_i} = \vec{0}` ; composée `g \circ f` ;
translation/rotation/homothétie `t_{\vec{u}}`, `r_{(\Omega,\theta)}`,
`h_{(\Omega,k)}` ; excentricité `e = \dfrac{MF}{MH}`.

**Suites** — `(u_n)` ; récurrence `u_{n+1} = f(u_n)` ; limite
`\lim_{n \to +\infty} u_n = \ell` ; encadrement avec `\leqslant` (jamais
`\le`).

**Logarithme / exponentielle** — `\ln x` (népérien) ; `\log_a x = \dfrac{\ln x}{\ln a}`
(base a) ; `\log x` (décimal) ; `e^x`, `e^{u(x)}` ; limites imposées par le
programme à respecter telles quelles (ex. `\lim_{x \to 0^+} x\ln x = 0`,
`\lim_{x \to +\infty} \dfrac{\ln x}{x^\alpha} = 0`).

**Continuité / dérivabilité** — dérivée `f'(x)`, `f''(x)` ; notation
différentielle `\dfrac{df}{dx}` ; dérivée de composée
`(f \circ g)' = (f' \circ g)\times g'` ; limites à gauche/droite `a^-`,
`a^+` ; réciproque `f^{-1}`.

**Étude de fonctions** — courbe `(\mathcal{C}_f)` ; asymptote `(\Delta)` ;
tangente `(T)`.

**Calcul intégral** — `\int_a^b f(x)\,dx` ; primitive `F` avec `F'=f` ;
crochet `\Big[F(x)\Big]_a^b` ; intégration par parties
`\int_a^b u'v = \Big[uv\Big]_a^b - \int_a^b uv'`.

**Équations différentielles** — `y' + ay = 0` (1er ordre),
`y'' + ay' + by = 0` (2e ordre).

**Probabilités / variables aléatoires** — probabilité `P(A)` ;
**conditionnelle** `P_B(A) = \dfrac{P(A \cap B)}{P(B)}` — **jamais**
`P(A\mid B)` ; coefficient binomial `\dbinom{n}{k}` ; espérance `E(X)` ;
variance `V(X)` ; écart-type `\sigma(X)` ; loi binomiale `\mathcal{B}(n,\,p)`.

**Statistiques à deux variables** — point moyen `G(\bar{x},\bar{y})` ;
covariance `\mathrm{Cov}(x,y)` ; coefficient de corrélation `r`.

## G. Les 3 marqueurs à ne JAMAIS confondre

| Concept | ✅ FAHIMTANA (français) | ❌ à bannir (anglo) |
|---------|------------------------|---------------------|
| Probabilité conditionnelle | `P_B(A)` | `P(A\mid B)` |
| PGCD / PPCM | `\mathrm{PGCD}` / `\mathrm{PPCM}` | `\gcd` / `\mathrm{lcm}` |
| Intervalle ouvert | `]a,b[` | `(a,b)` |

Inégalités **à la française** : `\leqslant` / `\geqslant` (barres obliques),
jamais `\le` / `\ge`.
"""


def inserer_charte_initiale(apps, schema_editor):
    CharteNotation = apps.get_model('programme', 'CharteNotation')
    if CharteNotation.objects.exists():
        return  # amorce déjà faite (ou charte créée manuellement) : ne rien écraser
    CharteNotation.objects.create(
        libelle="Charte de notation FAHIMTANA",
        contenu=CONTENU_INITIAL,
        active=True,
    )


def supprimer_charte_initiale(apps, schema_editor):
    CharteNotation = apps.get_model('programme', 'CharteNotation')
    CharteNotation.objects.filter(libelle="Charte de notation FAHIMTANA").delete()


class Migration(migrations.Migration):

    dependencies = [
        ('programme', '0006_charte_notation'),
    ]

    operations = [
        migrations.RunPython(inserer_charte_initiale, supprimer_charte_initiale),
    ]
