import os
import sys

# Fichiers d'entrée et de sortie
FICHIER_CONF_1 = "conf_1.txt"
FICHIER_CONF_2 = "conf_2.txt"
FICHIER_FUSIONNE = "liste_fusionnee.txt"

# Types de sections supportées
SECTIONS_SUPPORTÉES = [
    "config firewall address",
    "config firewall multicast-address",
    "config firewall address6",
    "config firewall multicast-address6",
    "config firewall addrgrp",
    "config firewall wildcard-fqdn custom"
]

# Fonction de lecture des sections pour en extraire les adresses/informations utiles
def lire_sections_fortigate(chemin_fichier, sections_demandées):
    """
    Lit un fichier FortiGate et extrait les objets d'adresses pour les sections demandées.
    Ignore les champs 'uuid'.
    Retourne un dictionnaire {section: liste d'objets}.
    """
    objets = {section: [] for section in sections_demandées}
    try:
        with open(chemin_fichier, 'r') as f:
            lignes = f.readlines()

        i = 0
        section_active = None
        while i < len(lignes):
            ligne = lignes[i].strip()

            # Détection du début d'une section pertinente
            if ligne in sections_demandées:
                section_active = ligne
                i += 1
                continue

            # Lecture des objets dans la section active
            if section_active and ligne.startswith("edit "):
                objet = {'name': ligne.split(maxsplit=1)[1].strip('"')}
                params = {}
                i += 1

                # Parcours des paramètres jusqu'à "next"
                while i < len(lignes):
                    l = lignes[i].strip()
                    if l == "next":
                        break
                    if l.startswith("set "):
                        partie = l[4:]
                        if ' ' in partie:
                            cle, val = partie.split(maxsplit=1)
                            if cle != "uuid":  # on ignore les UUIDs
                                params[cle] = val.strip('"')
                    i += 1

                objet.update(params)
                objets[section_active].append(objet)

            # Fin de section
            if ligne == "end":
                section_active = None

            i += 1

    except FileNotFoundError:
        print(f"Erreur : Le fichier '{chemin_fichier}' n'a pas été trouvé.")
    except Exception as e:
        print(f"Erreur lors de la lecture de '{chemin_fichier}' : {e}")

    return objets

# Fonction d'écriture des sections pour y retranscrire une fusion entre deux fichiers de config
def ecrire_sections_fortigate(chemin_fichier, objets_par_section):
    """
    Écrit les objets FortiGate dans un fichier de configuration FortiGate,
    en respectant l'ordre et la structure des sections.
    """
    try:
        with open(chemin_fichier, 'w') as f:
            for section in SECTIONS_SUPPORTÉES:
                if section in objets_par_section and objets_par_section[section]:
                    f.write(f"{section}\n")
                    for obj in objets_par_section[section]:
                        f.write(f"    edit \"{obj['name']}\"\n")
                        for k, v in obj.items():
                            if k != "name":
                                f.write(f"        set {k} \"{v}\"\n")
                        f.write("    next\n")
                    f.write("end\n\n")
        print(f"La liste fusionnée a été enregistrée dans '{chemin_fichier}'.")
    except Exception as e:
        print(f"Erreur lors de l'écriture du fichier '{chemin_fichier}' : {e}")

# Fonction de fusion des objets provenant de deux fichiers, avec priorité à conf_2 (conf_2)
def fusionner_sections(objets_conf_1, objets_conf_2):
    """
    Fusionne deux dictionnaires contenant les objets FortiGate extraits de fichiers différents.
    En cas de doublon de nom dans une même section, l'objet de 'objets_conf_2' (conf_2) est conservé.
    Retourne le résultat de la fusion ET un dict des doublons par section.
    """
    fusion = {}
    doublons = {}
    for section in SECTIONS_SUPPORTÉES:
        fusion[section] = {}
        conf_1_objs = {obj['name']: obj for obj in objets_conf_1.get(section, [])}
        conf_2_objs = {obj['name']: obj for obj in objets_conf_2.get(section, [])}

        # Ajouter les objets conf_1
        fusion[section].update(conf_1_objs)
        # Ajouter/écraser par les objets conf_2
        doublons_section = set()
        for name, obj in conf_2_objs.items():
            if name in fusion[section]:
                print(f"{COLOR_YELLOW}Avertissement : L'objet '{name}' est présent dans conf_1 et conf_2 ({section}). "
                      f"Celui de conf_2 sera conservé.{COLOR_RESET}")
                doublons_section.add(name)
            fusion[section][name] = obj
        doublons[section] = doublons_section

    # Convertir en listes
    return {k: list(v.values()) for k, v in fusion.items()}, doublons

# Fonction interactive pour demander à l'utilisateur quelles sections il souhaite traiter
def demander_sections():
    """
    Affiche une liste des sections supportées et permet à l'utilisateur d'en sélectionner plusieurs.
    Retourne une liste des sections choisies.
    """
    print("Sections disponibles :")
    for idx, section in enumerate(SECTIONS_SUPPORTÉES, 1):
        print(f"{idx}. {section}")
    choix = input("Entrez les numéros des sections à inclure, séparés par des virgules (ex: 1,3,6): ")
    try:
        indices = [int(i.strip()) for i in choix.split(',')]
        return [SECTIONS_SUPPORTÉES[i - 1] for i in indices if 0 < i <= len(SECTIONS_SUPPORTÉES)]
    except:
        print("Entrée invalide. Toutes les sections seront sélectionnées.")
        return SECTIONS_SUPPORTÉES

# Ajout de couleurs ANSI pour Windows (si supporté)
if os.name == 'nt':
    os.system('')  # Active les séquences ANSI sur Windows 10+

COLOR_RESET = "\033[0m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_BLUE = "\033[94m"
COLOR_MAGENTA = "\033[95m"

# Fonction pour afficher les objets fusionnés sous forme de tableau
def afficher_tableau(objets_fusionnés, sections_demandées, max_lignes=50):
    """
    Affiche les objets fusionnés sous forme de tableau pour chaque section sélectionnée.
    Utilise tabulate si disponible, sinon fallback sur affichage manuel.
    """
    try:
        from tabulate import tabulate
        tabulate_dispo = True
    except ImportError:
        tabulate_dispo = False

    for section in sections_demandées:
        objets = objets_fusionnés.get(section, [])
        if not objets:
            continue
        print(f"\n{COLOR_BLUE}╔════════════════════════════════════════════════════════════════════╗{COLOR_RESET}")
        print(f"{COLOR_BLUE}║ Section : {section:<56}║{COLOR_RESET}")
        print(f"{COLOR_BLUE}╚════════════════════════════════════════════════════════════════════╝{COLOR_RESET}")

        # Déterminer tous les attributs présents dans cette section
        attributs = set()
        for obj in objets:
            attributs.update(obj.keys())
        attributs = sorted([a for a in attributs if a != "name"])
        colonnes = ["name"] + attributs

        # Limite d'affichage
        objets_affiches = objets[:max_lignes]
        if tabulate_dispo:
            # Coloration de l'en-tête
            headers = [f"{COLOR_MAGENTA}{col.upper()}{COLOR_RESET}" for col in colonnes]
            table = []
            for obj in objets_affiches:
                row = [str(obj.get(col, ""))[:40] for col in colonnes]
                table.append(row)
            print(tabulate(table, headers=headers, tablefmt="fancy_grid", stralign="left", numalign="left", maxcolwidths=40))
        else:
            # Affichage manuel amélioré
            largeurs = {col: min(40, max(len(col), max((len(str(obj.get(col, ""))) for obj in objets_affiches), default=0))) for col in colonnes}
            ligne_entete = "│ " + " │ ".join(f"{COLOR_MAGENTA}{col.upper():<{largeurs[col]}}{COLOR_RESET}" for col in colonnes) + " │"
            separateur = "├" + "─" * (len(ligne_entete) - 2) + "┤"
            print("┌" + "─" * (len(ligne_entete) - 2) + "┐")
            print(ligne_entete)
            print(separateur)
            for obj in objets_affiches:
                ligne = "│ " + " │ ".join(
                    f"{str(obj.get(col, '')).replace(chr(10),' ')[:largeurs[col]]:<{largeurs[col]}}" for col in colonnes
                ) + " │"
                print(ligne)
            print("└" + "─" * (len(ligne_entete) - 2) + "┘")
            if not tabulate_dispo:
                print(f"{COLOR_YELLOW}Pour un affichage optimal, installez 'tabulate' (pip install tabulate).{COLOR_RESET}")

        if len(objets) > max_lignes:
            print(f"{COLOR_YELLOW}... ({len(objets) - max_lignes} objets non affichés){COLOR_RESET}")

# Fonction principale
def main():
    """Point d’entrée principal"""
    print(f"{COLOR_BLUE}=== Fusion de configurations FortiGate ==={COLOR_RESET}")
    sections_demandées = demander_sections()

    print(f"\nLecture de '{FICHIER_CONF_1}'...")
    objets_conf_1 = lire_sections_fortigate(FICHIER_CONF_1, sections_demandées)

    print(f"\nLecture de '{FICHIER_CONF_2}'...")
    objets_conf_2 = lire_sections_fortigate(FICHIER_CONF_2, sections_demandées)

    print("\nFusion des objets...")
    objets_fusionnés, doublons = fusionner_sections(objets_conf_1, objets_conf_2)

    print("\nÉcriture du fichier fusionné...")
    ecrire_sections_fortigate(FICHIER_FUSIONNE, objets_fusionnés)

    print(f"\n{COLOR_GREEN} ✔ Fusion terminée. Résultat :{COLOR_RESET}")
    for section in sections_demandées:
        count_1 = len(objets_conf_1.get(section, []))
        count_2 = len(objets_conf_2.get(section, []))
        count_fusion = len(objets_fusionnés.get(section, []))
        nb_communs = len(doublons.get(section, []))
        total_uniques = len(set([obj['name'] for obj in objets_conf_1.get(section, [])] +
                                [obj['name'] for obj in objets_conf_2.get(section, [])]))
        percent_communs = (nb_communs / total_uniques * 100) if total_uniques else 0
        print(f" - {COLOR_BLUE}{section}{COLOR_RESET} : {COLOR_GREEN}{count_fusion} objets{COLOR_RESET} "
              f"({COLOR_MAGENTA}{percent_communs:.1f}%{COLOR_RESET} en commun, "
              f"{COLOR_GREEN}{count_1}{COLOR_RESET} conf_1, {COLOR_GREEN}{count_2}{COLOR_RESET} conf_2)")

    # Demander à l'utilisateur s'il veut afficher la liste fusionnée en format tableau
    afficher = input(f"\nVoulez-vous afficher la liste fusionnée au format tableau ? (o/n) : ").strip().lower()
    if afficher == "o":
        afficher_tableau(objets_fusionnés, sections_demandées)

if __name__ == "__main__":
    main()
