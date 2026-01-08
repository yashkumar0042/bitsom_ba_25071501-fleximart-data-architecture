/**
 * mongodb_operations.js
 */

use fleximart;

/* =========================
   Operation 1: Load Data 
   =========================
*/

try {
  const raw = cat("products_catalog.json"); // reads file as a string
  const docs = JSON.parse(raw);             // products_catalog.json should be a JSON array
  db.products.drop();                       // reset collection
  db.products.insertMany(docs);
  print(`Loaded ${docs.length} products into fleximart.products`);
} catch (e) {
  print("NOTE: Operation 1 (shell import) could not run. If cat() is unavailable, use mongoimport instead.");
  print(e);
}

/* =========================
   Operation 2: Basic Query 
   =========================
*/
print("\nOperation 2: Electronics under 50000 (name, price, stock)");
db.products.find(
  { category: "Electronics", price: { $lt: 50000 } },
  { _id: 0, name: 1, price: 1, stock: 1 }
).forEach(doc => printjson(doc));

/* =========================
   Operation 3: Review Analysis
   =========================
   */
print("\nOperation 3: Products with avg rating >= 4.0");
db.products.aggregate([
  
  { $match: { reviews: { $exists: true, $type: "array", $ne: [] } } },

  { $addFields: { avg_rating: { $avg: "$reviews.rating" }, review_count: { $size: "$reviews" } } },

  { $match: { avg_rating: { $gte: 4.0 } } },

  { $project: { _id: 0, product_id: 1, name: 1, category: 1, avg_rating: 1, review_count: 1 } },

  { $sort: { avg_rating: -1, review_count: -1 } }
]).forEach(doc => printjson(doc));

/* =========================
   Operation 4: Update Operation
   =========================
*/
print("\nOperation 4: Add review to ELEC001");
db.products.updateOne(
  { product_id: "ELEC001" },
  {
    $push: {
      reviews: {
        user: "U999",
        rating: 4,
        comment: "Good value",
        date: new Date() 
      }
    }
  }
);
print("Updated ELEC001 (pushed new review).");

/* =========================
   Operation 5: Complex Aggregation 
   =========================
*/
print("\nOperation 5: Avg price by category (desc)");
db.products.aggregate([
  {
    $group: {
      _id: "$category",
      avg_price: { $avg: "$price" },
      product_count: { $sum: 1 }
    }
  },
  {
    $project: {
      _id: 0,
      category: "$_id",
      avg_price: { $round: ["$avg_price", 2] },
      product_count: 1
    }
  },
  { $sort: { avg_price: -1 } }
]).forEach(doc => printjson(doc));

print("\nDone.");
