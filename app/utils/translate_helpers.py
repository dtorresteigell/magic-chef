# ============================================================================
# FILE: utils/translate_helpers.py
# ============================================================================

import asyncio
from googletrans import Translator

async def translate_text(txt, dest_lang='es'):
    """Basic async translation function"""
    async with Translator() as translator:
        result = await translator.translate(txt, dest=dest_lang)
    return result.text


async def translate_recipe_data(recipe_data, dest_lang='es'):
    """
    Efficiently translate recipe data by batching all translatable content.
    
    Args:
        recipe_data: Dict with keys: title, description, notes_list, 
                     ingredients_dict, instructions_list
        dest_lang: Target language code (en, es, de, tr)
    
    Returns:
        Dict with same structure but translated values
    """
    DELIMITER = " ||| "
    
    # Collect all texts to translate
    texts_to_translate = []
    metadata = []  # Track what each text is
    
    # 1. Title
    if recipe_data.get('title'):
        texts_to_translate.append(recipe_data['title'])
        metadata.append(('title', None))
    
    # 2. Description
    if recipe_data.get('description'):
        texts_to_translate.append(recipe_data['description'])
        metadata.append(('description', None))
    
    # 3. Notes
    if recipe_data.get('notes_list'):
        for idx, note in enumerate(recipe_data['notes_list']):
            texts_to_translate.append(note)
            metadata.append(('note', idx))
    
    # 4. Ingredients (both keys and values)
    if recipe_data.get('ingredients_dict'):
        for key, value in recipe_data['ingredients_dict'].items():
            texts_to_translate.append(key)
            metadata.append(('ingredient_key', key))
            texts_to_translate.append(value)
            metadata.append(('ingredient_value', key))
    
    # 5. Instructions
    if recipe_data.get('instructions_list'):
        for idx, instruction in enumerate(recipe_data['instructions_list']):
            texts_to_translate.append(instruction)
            metadata.append(('instruction', idx))
    
    # Batch translate with length limit check
    if not texts_to_translate:
        return recipe_data
    
    # Split into batches if needed (Google Translate ~5000 char limit)
    MAX_BATCH_LENGTH = 4500
    batches = []
    current_batch_texts = []
    current_batch_meta = []
    current_length = 0
    
    for text, meta in zip(texts_to_translate, metadata):
        text_length = len(text) + len(DELIMITER)
        if current_length + text_length > MAX_BATCH_LENGTH and current_batch_texts:
            batches.append((current_batch_texts, current_batch_meta))
            current_batch_texts = [text]
            current_batch_meta = [meta]
            current_length = text_length
        else:
            current_batch_texts.append(text)
            current_batch_meta.append(meta)
            current_length += text_length
    
    if current_batch_texts:
        batches.append((current_batch_texts, current_batch_meta))
    
    # Translate all batches
    all_translations = {}
    for batch_texts, batch_meta in batches:
        combined = DELIMITER.join(batch_texts)
        translated = await translate_text(combined, dest_lang)
        translated_list = translated.split(DELIMITER)
        
        for meta, trans in zip(batch_meta, translated_list):
            all_translations[meta] = trans.strip()
    
    # Reconstruct the recipe data
    result = {
        'title': '',
        'description': '',
        'notes_list': [],
        'ingredients_dict': {},
        'instructions_list': [],
        'servings': recipe_data.get('servings', 4),
        'tags_list': recipe_data.get('tags_list', []),  # Don't translate tags
    }
    
    # Apply translations
    if ('title', None) in all_translations:
        result['title'] = all_translations[('title', None)]
    
    if ('description', None) in all_translations:
        result['description'] = all_translations[('description', None)]
    
    # Reconstruct notes in order
    if recipe_data.get('notes_list'):
        result['notes_list'] = [
            all_translations[('note', idx)] 
            for idx in range(len(recipe_data['notes_list']))
        ]
    
    # Reconstruct ingredients with translated keys and values
    if recipe_data.get('ingredients_dict'):
        for original_key in recipe_data['ingredients_dict'].keys():
            trans_key = all_translations[('ingredient_key', original_key)]
            trans_value = all_translations[('ingredient_value', original_key)]
            result['ingredients_dict'][trans_key] = trans_value
    
    # Reconstruct instructions in order
    if recipe_data.get('instructions_list'):
        result['instructions_list'] = [
            all_translations[('instruction', idx)]
            for idx in range(len(recipe_data['instructions_list']))
        ]
    
    return result


def translate_recipe_sync(recipe_data, dest_lang='es'):
    """Synchronous wrapper for use in Flask routes"""
    return asyncio.run(translate_recipe_data(recipe_data, dest_lang))