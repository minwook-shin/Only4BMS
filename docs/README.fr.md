# Only4BMS

<img width="2556" height="1439" alt="스크린샷 2026-02-24 230333" src="https://github.com/user-attachments/assets/68d1891b-891b-4927-ab81-96f7bbc098f7" />

[![Only4BMS AI Battle1](https://img.youtube.com/vi/mrSUp4h7DnE/0.jpg)](https://youtu.be/mrSUp4h7DnE)

7 touches ? Non merci. 

Il s'agit d'un lecteur BMS basé sur Pygame qui **réorganise de force** tous les graphiques BMS en **4 touches (DFJK)** pour la lecture.

## Présentation du projet

Only4BMS a été créé pour les puristes du 4 touches qui font face à des graphiques BMS complexes comme le 7 touches ou le 14 touches et se disent : « Comment suis-je censé jouer tout ça ? »

Ce projet utilise Pygame pour analyser les fichiers BMS et fournit un environnement où vous pouvez profiter de n'importe quel format de graphique **remappé en 4 pistes** avec des sons de touches (keysounds).

## Caractéristiques principales

**Mappage forcé en 4 touches** : attribue automatiquement les graphiques à 5 touches, 7 touches, 10 touches et 14 touches à 4 pistes (D, F, J, K) à l'aide d'algorithmes mathématiques.

**Vérificateur de densité** : vérifie et visualise la densité des notes lorsque les graphiques à 7 touches sont consolidés en 4 touches.

## 🛠️ Technologies utilisées

**Langage** : Python 3.x

**Bibliothèque** : Pygame (Son et Rendu)

**Format** : Be-Music Script (.bms, .bme, .bml)

## Comment jouer (Ajout de morceaux et exécution)

1. **Obtenir le jeu** : Téléchargez l'exécutable `Only4BMS.exe` pré-construit ou construisez-le vous-même.
2. **Lancer** : Exécutez simplement `Only4BMS.exe` depuis n'importe quel dossier. 
3. **Le dossier `bms`** : Au lancement, le jeu crée automatiquement un dossier `bms` dans le même répertoire que l'exécutable. Si aucun morceau n'est trouvé, il génère un morceau de démonstration de base.
4. **Ajouter vos propres morceaux** : 
   - Téléchargez les fichiers BMS/BME/BML et leurs supports associés (audio/vidéos BGA).
   - Extrayez-les dans leurs propres sous-dossiers à l'intérieur du répertoire `bms/`.
   - Exemple de structure :
     ```text
     [Répertoire contenant Only4BMS.exe]
     ├── Only4BMS.exe
     └── bms/
         ├── Awesome Track/
         │   ├── song.bms
         │   ├── audio.wav
         │   └── video.mp4
         └── Another Track/
             └── ...
     ```

## 🤖 Entraînement de l'IA et multijoueur

Only4BMS propose un mode multijoueur IA alimenté par l'**apprentissage par renforcement (PPO)**.

### Comment ça marche
- L'IA est entraînée à l'aide de `stable-baselines3` sur des pistes rythmiques générées de manière procédurale et des morceaux de démonstration libres de droits.
- **Conformité légale** : Pour garantir des normes éthiques, les versions officielles incluent des modèles entraînés *exclusivement* sur des données non commerciales pendant le processus CI/CD.
- **Difficultés** :
  - **NORMAL** : Entraînée pendant 25 000 étapes. Haute précision mais erreurs occasionnelles de type humain.
  - **HARD** : Entraînée pendant 40 000 étapes. Timing et maintien de combo presque parfaits.

### Entraînement local
Si vous souhaitez entraîner vos propres modèles localement :
1. Installez les dépendances : `pip install stable-baselines3 shimmy gymnasium torch`
2. Exécutez le script d'entraînement : `python -m only4bms.ai.train`
3. Les fichiers `model_normal.zip` et `model_hard.zip` générés seront sauvegardés dans `src/only4bms/ai/`.

### CI/CD automatisé
Notre flux de travail GitHub Actions réentraîne automatiquement les modèles d'IA à partir de zéro en utilisant la `Mock Song Demo` pour chaque version. Cela garantit que le binaire distribué aux utilisateurs est toujours « propre » et optimisé.

<a href="https://minwook-shin.itch.io/only4bms" class="btn">Jouer sur itch.io</a>

## Déclaration de transparence :

Only4BMS est un projet solo passionné.

Pour rationaliser le processus de production, j'ai incorporé une technologie assistée par IA pour le code.

Cela m'a permis de repousser les limites de ce qu'une seule personne peut créer, en veillant à ce que le jeu final soit peaufiné et complet.

## 🤝 Contribuer

Les rapports de bogues et les suggestions de fonctionnalités des utilisateurs de 4 touches sont toujours les bienvenus !

## 📜 Licence

Licence MIT - N'hésitez pas à modifier et à distribuer. S'il vous plaît, gardez juste la paix pour les utilisateurs de 4 touches.
