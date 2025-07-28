import os

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
    """
    fusion = {}
    for section in SECTIONS_SUPPORTÉES:
        fusion[section] = {}
        conf_1_objs = {obj['name']: obj for obj in objets_conf_1.get(section, [])}
        conf_2_objs = {obj['name']: obj for obj in objets_conf_2.get(section, [])}

        # Ajouter les objets conf_1
        fusion[section].update(conf_1_objs)
        # Ajouter/écraser par les objets conf_2
        for name, obj in conf_2_objs.items():
            if name in fusion[section]:
                print(f"Avertissement : L'objet '{name}' est présent dans conf_1 et conf_2 ({section}). "
                      f"Celui de conf_2 sera conservé.")
            fusion[section][name] = obj

    # Convertir en listes
    return {k: list(v.values()) for k, v in fusion.items()}

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

# Fonction principale
def main():
    """Point d’entrée principal"""
    print("=== Fusion de configurations FortiGate ===")
    sections_demandées = demander_sections()

    print(f"\nLecture de '{FICHIER_CONF_1}'...")
    objets_conf_1 = lire_sections_fortigate(FICHIER_CONF_1, sections_demandées)

    print(f"\nLecture de '{FICHIER_CONF_2}'...")
    objets_conf_2 = lire_sections_fortigate(FICHIER_CONF_2, sections_demandées)

    print("\nFusion des objets...")
    objets_fusionnés = fusionner_sections(objets_conf_1, objets_conf_2)

    print("\nÉcriture du fichier fusionné...")
    ecrire_sections_fortigate(FICHIER_FUSIONNE, objets_fusionnés)

    print("\n ✔ Fusion terminée. Résultat :")
    for section in sections_demandées:
        count = len(objets_fusionnés.get(section, []))
        print(f" - {section} : {count} objets")

if __name__ == "__main__":
    main()
