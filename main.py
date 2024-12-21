def generate_csv():
    """Generate CSV from scraped products with enhanced error handling"""
    try:
        start_page = int(request.form.get('start_page', 1))
        end_page = int(request.form.get('end_page', 50))
        
        if start_page < 1 or end_page > 4331:
            raise ValueError("Invalid page range")
        if start_page > end_page:
            raise ValueError("Start page must be less than end page")
            
        # Use the enhanced scraper with progress callback
        products = scrape_acdc_products(
            start_page=start_page,
            end_page=end_page,
            progress_callback=emit_progress,
            cancel_event=cancel_event
        )
        
        if products:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = os.path.join('/tmp', f'acdc_products_{start_page}_to_{end_page}_{timestamp}.csv')
            saved_file = save_to_csv(products, filename)
            
            # Final progress update
            emit_progress(
                f'Scraping completed! Found {len(products)} products',
                end_page - start_page + 1,
                end_page - start_page + 1,
                'success'
            )
            
            return saved_file
    except Exception as e:
        emit_progress(
            f'Error: {str(e)}',
            0,
            100,
            'error'
        )
        return None
